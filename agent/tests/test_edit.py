"""Conversational editing — ops applied to a plan, and the node that drives them.

The bug these guard: a follow-up prompt used to be a fresh generation with no idea what
was on screen, so "add cylinders where it makes sense" drew an unrelated diagram.
"""

from __future__ import annotations

import asyncio

from app.graph import nodes
from app.graph.apply_ops import apply_ops
from app.graph.edit_llm import DiagramEdit, EditOp
from app.graph.planner_llm import DiagramPlan, PlanEdge, PlanGroup, PlanNode


def _plan() -> DiagramPlan:
    return DiagramPlan(
        title="Web Persistence",
        nodes=[
            PlanNode(id="client", label="Client", kind="client", group="g1"),
            PlanNode(id="api", label="API Gateway", kind="service", group="g1"),
            PlanNode(id="db", label="Primary Database", group="g2"),
            PlanNode(id="cache", label="In-Memory Cache", group="g2"),
        ],
        edges=[
            PlanEdge(source="client", target="api", label="request"),
            PlanEdge(source="api", target="db", label="write"),
            PlanEdge(source="api", target="cache", label="read"),
        ],
        groups=[PlanGroup(id="g1", label="1. Edge"), PlanGroup(id="g2", label="2. Storage")],
    )


def _op(op: str, **kw) -> EditOp:
    return EditOp(op=op, **kw)


# --- applying operations -----------------------------------------------------------------


def test_the_reported_case_turning_stores_into_cylinders():
    result = apply_ops(
        _plan(),
        [
            _op("update_node", id="db", kind="datastore"),
            _op("update_node", id="cache", kind="datastore"),
        ],
    )
    kinds = {n.id: n.kind for n in result.plan.nodes}
    assert kinds["db"] == "datastore" and kinds["cache"] == "datastore"
    assert kinds["client"] == "client", "an edit must not touch what it wasn't asked about"
    assert len(result.applied) == 2 and not result.rejected


def test_the_callers_plan_is_never_mutated():
    original = _plan()
    apply_ops(original, [_op("remove_node", id="db"), _op("set_title", title="Gone")])
    assert [n.id for n in original.nodes] == ["client", "api", "db", "cache"]
    assert original.title == "Web Persistence"


def test_removing_a_node_takes_its_connections():
    result = apply_ops(_plan(), [_op("remove_node", id="db")])
    assert "db" not in {n.id for n in result.plan.nodes}
    assert all("db" not in (e.source, e.target) for e in result.plan.edges)
    assert "2 connection" not in result.applied[0]  # db had exactly one
    assert "1 connection" in result.applied[0]


def test_unknown_ids_are_rejected_and_reported_not_invented():
    result = apply_ops(
        _plan(),
        [
            _op("update_node", id="ghost", kind="datastore"),
            _op("add_edge", source="client", target="ghost"),
            _op("remove_edge", source="db", target="client"),
        ],
    )
    assert not result.applied
    assert len(result.rejected) == 3
    assert len(result.plan.nodes) == 4, "a rejected op must change nothing"


def test_adding_a_node_and_wiring_it_in():
    result = apply_ops(
        _plan(),
        [
            _op("add_node", id="queue", label="Event Queue", kind="queue", group="g2"),
            _op("add_edge", source="api", target="queue", label="publish"),
        ],
    )
    added = next(n for n in result.plan.nodes if n.id == "queue")
    assert added.kind == "queue" and added.group == "g2"
    assert any(e.source == "api" and e.target == "queue" for e in result.plan.edges)


def test_a_node_added_to_a_phase_that_does_not_exist_stays_ungrouped():
    result = apply_ops(_plan(), [_op("add_node", id="x", label="X", group="nope")])
    assert next(n for n in result.plan.nodes if n.id == "x").group is None
    assert result.rejected, "silently dropping the group would hide the mistake"


def test_dissolving_a_phase_keeps_its_members():
    result = apply_ops(_plan(), [_op("remove_group", id="g2")])
    assert [g.id for g in result.plan.groups] == ["g1"]
    assert {n.id for n in result.plan.nodes} == {"client", "api", "db", "cache"}
    assert all(n.group != "g2" for n in result.plan.nodes)


def test_duplicate_and_self_edges_are_refused():
    result = apply_ops(
        _plan(),
        [
            _op("add_edge", source="client", target="api"),
            _op("add_edge", source="api", target="api"),
        ],
    )
    assert not result.applied and len(result.rejected) == 2


def test_relabelling_edges_and_retitling():
    result = apply_ops(
        _plan(),
        [
            _op("update_edge", source="api", target="db", label="persist"),
            _op("set_title", title="Storage Path"),
        ],
    )
    edge = next(e for e in result.plan.edges if e.target == "db")
    assert edge.label == "persist" and result.plan.title == "Storage Path"


# --- the editor node ----------------------------------------------------------------------


def _run_editor(monkeypatch, edit: DiagramEdit | None, base: DiagramPlan | None = None) -> dict:
    async def fake_propose(*_args, **_kwargs):
        return edit

    monkeypatch.setattr(nodes, "propose_edit", fake_propose)
    state = {
        "input_kind": "text",
        "payload": "add cylindrical shapes where it makes sense",
        "base_plan": _plan() if base is None else base,
    }
    return asyncio.run(nodes.editor(state))


def test_an_edit_produces_a_plan_so_the_create_path_is_skipped(monkeypatch):
    out = _run_editor(
        monkeypatch,
        DiagramEdit(
            intent="edit",
            ops=[EditOp(op="update_node", id="db", kind="datastore")],
            summary="made the database a cylinder",
        ),
    )
    assert out["llm_plan"].nodes, "the planner reads this and steps aside"
    assert out["plan_report"]["intent"] == "edit"
    assert out["plan_report"]["applied"] == ["Primary Database: kind → datastore"]


def test_replace_hands_back_to_the_create_path(monkeypatch):
    out = _run_editor(monkeypatch, DiagramEdit(intent="replace", ops=[]))
    assert out == {"base_plan": None}, "no plan, so specifier and planner run normally"


def test_a_failed_edit_call_leaves_the_diagram_alone(monkeypatch):
    assert _run_editor(monkeypatch, None) == {}


def test_the_first_prompt_has_nothing_to_edit(monkeypatch):
    empty = DiagramPlan(nodes=[], edges=[])
    assert _run_editor(monkeypatch, DiagramEdit(intent="edit"), base=empty) == {}


def test_an_edit_that_would_empty_the_diagram_is_refused(monkeypatch):
    out = _run_editor(
        monkeypatch,
        DiagramEdit(
            intent="edit",
            ops=[EditOp(op="remove_node", id=n) for n in ("client", "api", "db", "cache")],
        ),
    )
    assert out["plan_report"]["nodes"] == 4, "the previous diagram survives"
    assert any("whole diagram" in r for r in out["plan_report"]["rejected"])


def test_a_question_is_answered_and_nothing_is_drawn(monkeypatch):
    out = _run_editor(
        monkeypatch,
        DiagramEdit(intent="answer", reply="The cache is read before the database."),
    )
    assert out == {"answered": True, "reply": "The cache is read before the database."}
    assert "llm_plan" not in out, "an answer must not hand the drawer anything"


def test_an_empty_answer_still_says_something(monkeypatch):
    out = _run_editor(monkeypatch, DiagramEdit(intent="answer", reply="   "))
    assert out["reply"], "a blank reply would look like the app hung"


def test_an_edit_with_no_changes_keeps_the_diagram(monkeypatch):
    out = _run_editor(monkeypatch, DiagramEdit(intent="edit", ops=[], summary="nothing to change"))
    assert out["plan_report"]["applied"] == []
    assert out["plan_report"]["nodes"] == 4


# --- graph wiring -------------------------------------------------------------------------


def test_the_graph_stops_at_an_answer_and_draws_nothing(monkeypatch):
    from app.graph.build import build_graph

    async def fake_propose(*_args, **_kwargs):
        return DiagramEdit(intent="answer", reply="Because the gateway checks it first.")

    monkeypatch.setattr(nodes, "propose_edit", fake_propose)
    state = {
        "input_kind": "text",
        "payload": "why does the gateway sit before the service?",
        "base_plan": _plan(),
        "iterations": 0,
    }
    visited = [name for name, _ in asyncio.run(_walk(build_graph(), state))]
    assert visited == ["router", "editor"], f"drew anyway: {visited}"
    assert not state.get("actions")
    assert state["reply"].startswith("Because")


async def _walk(graph, state):
    return [step async for step in graph.astream(state)]


def test_an_edit_walks_all_the_way_to_the_critic(monkeypatch):
    from app.graph.build import build_graph

    async def fake_propose(*_args, **_kwargs):
        return DiagramEdit(intent="edit", ops=[EditOp(op="update_node", id="db", kind="datastore")])

    monkeypatch.setattr(nodes, "propose_edit", fake_propose)
    state = {
        "input_kind": "text",
        "payload": "make the database a cylinder",
        "base_plan": _plan(),
        "vision_enabled": False,
        "layout_params": {"gap_scale": 1.0},
        "iterations": 0,
    }
    visited = [name for name, _ in asyncio.run(_walk(build_graph(), state))]
    assert visited[:2] == ["router", "editor"]
    assert "drawer" in visited and "critic" in visited
    assert state["actions"], "an edit still redraws through the normal pipeline"
