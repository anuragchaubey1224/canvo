"""Deterministic test for the LLM-plan layout (no network/LLM)."""

from __future__ import annotations

from app.graph.layout import build_graph_actions
from app.graph.planner_llm import DiagramPlan, PlanEdge, PlanNode


def test_build_graph_actions():
    plan = DiagramPlan(
        nodes=[PlanNode(id="login", label="Login"), PlanNode(id="dash", label="Dashboard")],
        edges=[PlanEdge(source="login", target="dash", label="ok")],
    )
    actions = build_graph_actions(plan)

    boxes = {a.shape.id for a in actions if a.shape and a.shape.type == "geo"}
    arrows = [a for a in actions if a.shape and a.shape.type == "arrow"]

    assert {"n-login", "n-dash"} <= boxes
    assert any(x.shape.from_id == "n-login" and x.shape.to_id == "n-dash" for x in arrows)
