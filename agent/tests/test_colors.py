"""Colour survives whatever the planner invents (deterministic, no LLM).

The client greys out any colour token it can't render, so an unvalidated planner value
drains the whole diagram — that is exactly what a model swap once did in production.
"""

from __future__ import annotations

from app.graph.layout import build_graph_actions
from app.graph.planner_llm import DiagramPlan, PlanEdge, PlanGroup, PlanNode
from app.schema import COLOR_TOKENS, color_token


def _plan(*group_colors: str | None) -> DiagramPlan:
    nodes, edges, groups = [], [], []
    for i, col in enumerate(group_colors, 1):
        groups.append(PlanGroup(id=f"g{i}", label=f"{i}. Phase", color=col))
        nodes += [PlanNode(id=f"n{i}a", label="A", group=f"g{i}")]
        nodes += [PlanNode(id=f"n{i}b", label="B", group=f"g{i}")]
        edges.append(PlanEdge(source=f"n{i}a", target=f"n{i}b"))
    return DiagramPlan(title="T", nodes=nodes, edges=edges, groups=groups)


def _colors(plan: DiagramPlan, shape_type: str) -> list[str | None]:
    return [a.shape.color for a in build_graph_actions(plan) if a.shape.type == shape_type]


def test_normaliser_accepts_tokens_and_rejects_inventions():
    assert color_token("blue") == "blue"
    assert color_token(" Light Blue ") == "light-blue"  # case and spacing are forgivable
    assert color_token("light_blue") == "light-blue"
    for invented in ("#3B82F6", "blue-500", "primary", "rgb(1,2,3)", "", None):
        assert color_token(invented) is None


def test_hex_and_shade_names_fall_back_to_a_real_palette():
    panels = _colors(_plan("#3B82F6", "blue-500", "primary"), "container")
    assert len(panels) == 3
    assert all(c in COLOR_TOKENS for c in panels)
    assert len(set(panels)) == 3  # and they stay distinguishable from each other


def test_a_valid_planner_colour_is_honoured():
    assert _colors(_plan("violet", "orange"), "container") == ["violet", "orange"]


def test_cards_and_arrows_inherit_a_renderable_accent():
    plan = _plan("#BADC0DE")
    assert all(c in COLOR_TOKENS for c in _colors(plan, "geo"))
    assert all(c in COLOR_TOKENS for c in _colors(plan, "arrow"))


def test_missing_colours_still_produce_distinct_panels():
    panels = _colors(_plan(None, None, None), "container")
    assert len(set(panels)) == 3 and all(c in COLOR_TOKENS for c in panels)
