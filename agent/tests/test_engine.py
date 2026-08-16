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
