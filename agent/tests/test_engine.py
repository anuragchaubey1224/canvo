"""Canvo's own graph engine — orchestration primitives (sync/async, loops, streaming)."""

from __future__ import annotations

import asyncio

import pytest

from app.graph.engine import END, Graph


def test_linear_runs_in_order_and_merges_state():
    order: list[str] = []

    def a(_s):
        order.append("a")
        return {"a": 1}

    async def b(s):  # async node is awaited
        order.append("b")
        return {"b": s["a"] + 1}

    g = Graph()
    g.add_node("a", a)
    g.add_node("b", b)
    g.set_entry("a")
    g.add_edge("a", "b")
    g.add_edge("b", END)

    result = asyncio.run(g.ainvoke({}))
    assert order == ["a", "b"]
    assert result == {"a": 1, "b": 2}


def test_conditional_loop_converges():
    def step(s):
        return {"n": s.get("n", 0) + 1}

    def route(s):
        return "loop" if s["n"] < 3 else "done"

    g = Graph()
    g.add_node("step", step)
    g.set_entry("step")
    g.add_conditional("step", route, {"loop": "step", "done": END})

    result = asyncio.run(g.ainvoke({}))
    assert result["n"] == 3


def test_astream_yields_each_delta_not_full_state():
    g = Graph()
    g.add_node("a", lambda _s: {"x": 1})
    g.add_node("b", lambda _s: {"y": 2})
    g.set_entry("a")
    g.add_edge("a", "b")
    g.add_edge("b", END)

    async def collect():
        return [(node, dict(update)) async for node, update in g.astream({})]

    assert asyncio.run(collect()) == [("a", {"x": 1}), ("b", {"y": 2})]


def test_step_cap_guards_infinite_loop():
    g = Graph()
    g.add_node("step", lambda _s: {})
    g.set_entry("step")
    g.add_conditional("step", lambda _s: "loop", {"loop": "step"})  # never reaches END

    with pytest.raises(RuntimeError, match="infinite loop"):
        asyncio.run(g.ainvoke({}))


def test_unmapped_router_key_raises():
    g = Graph()
    g.add_node("step", lambda _s: {})
    g.set_entry("step")
    g.add_conditional("step", lambda _s: "surprise", {"loop": "step"})

    with pytest.raises(KeyError):
        asyncio.run(g.ainvoke({}))


# --- Phase 01: per-stage timing -----------------------------------------------------------


def test_astream_reports_how_long_each_node_took():
    """`on_step` is a callback rather than a key written into state, so instrumentation
    can never collide with a node's own update."""
    import asyncio

    g = Graph()
    g.add_node("a", lambda s: {"a": 1})
    g.add_node("b", lambda s: {"b": 2})
    g.set_entry("a")
    g.add_edge("a", "b")

    seen: list[tuple[str, float]] = []

    async def run():
        async for _node, _update in g.astream({}, lambda n, ms: seen.append((n, ms))):
            pass

    asyncio.run(run())

    assert [name for name, _ in seen] == ["a", "b"]
    assert all(ms >= 0 for _, ms in seen)


def test_a_node_that_runs_twice_is_reported_twice():
    """The drawer runs again on a refine. Summing is the caller's business, not the
    engine's — it reports each visit."""
    import asyncio

    g = Graph()
    calls = {"n": 0}

    def draw(state):
        calls["n"] += 1
        return {"drawn": calls["n"]}

    g.add_node("draw", draw)
    g.add_node("check", lambda s: {})
    g.set_entry("draw")
    g.add_edge("draw", "check")
    g.add_conditional("check", lambda s: "again" if s["drawn"] < 2 else "stop",
                      {"again": "draw", "stop": END})

    seen: list[str] = []
    asyncio.run(g.ainvoke({}, lambda n, ms: seen.append(n)))

    assert seen.count("draw") == 2


def test_timing_is_optional():
    """Every existing caller passes nothing, and must keep working."""
    import asyncio

    g = Graph()
    g.add_node("only", lambda s: {"ok": True})
    g.set_entry("only")

    assert asyncio.run(g.ainvoke({}))["ok"] is True
