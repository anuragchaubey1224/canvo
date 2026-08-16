"""Orthogonal router — obstacle avoidance (deterministic, no network/LLM)."""

from __future__ import annotations

from app.graph.critique import analyze_geometry
from app.graph.layout import build_graph_actions
from app.graph.planner_llm import DiagramPlan, PlanEdge, PlanGroup, PlanNode
from app.graph.route import route_arrows
from app.schema import AgentAction, Shape


def _box(box_id: str, x: float, y: float, w: float = 200, h: float = 64) -> AgentAction:
    return AgentAction(type="create", shape=Shape(id=box_id, type="geo", x=x, y=y, w=w, h=h))


def _arrow(arrow_id: str, frm: str, to: str, text: str = "") -> AgentAction:
    return AgentAction(
        type="create",
        shape=Shape(id=arrow_id, type="arrow", x=0, y=0, from_id=frm, to_id=to, text=text),
    )


def _segments(points: list[float]):
    pts = list(zip(points[::2], points[1::2], strict=False))
    return list(zip(pts, pts[1:], strict=False))


def _hits(points: list[float], rect: Shape) -> bool:
    for (ax, ay), (bx, by) in _segments(points):
        lo_x, hi_x = min(ax, bx), max(ax, bx)
        lo_y, hi_y = min(ay, by), max(ay, by)
        if lo_x < rect.x + rect.w and hi_x > rect.x and lo_y < rect.y + rect.h and hi_y > rect.y:
            return True
    return False


def test_route_detours_around_a_blocking_box():
    # a → c with b directly in between: a straight elbow would cut through b.
    actions = route_arrows(
        [_box("a", 0, 0), _box("b", 400, 0), _box("c", 800, 0), _arrow("e", "a", "c")]
    )
    arrow = next(x.shape for x in actions if x.shape and x.shape.type == "arrow")
    assert arrow.points and len(arrow.points) >= 6  # detour needs at least one bend
    assert not _hits(arrow.points, next(x.shape for x in actions if x.shape.id == "b"))
    # and the critic agrees: no arrow_crossing on the routed path
    assert not any(i.kind == "arrow_crossing" for i in analyze_geometry(actions).issues)


def test_routes_are_orthogonal():
    actions = route_arrows([_box("a", 0, 0), _box("b", 400, 300), _arrow("e", "a", "b")])
    arrow = next(x.shape for x in actions if x.shape and x.shape.type == "arrow")
    assert arrow.points
    for (ax, ay), (bx, by) in _segments(arrow.points):
        assert ax == bx or ay == by  # every segment axis-aligned


def test_label_anchor_sits_on_the_route():
    actions = route_arrows([_box("a", 0, 0), _box("b", 800, 0), _arrow("e", "a", "b", text="ok")])
    arrow = next(x.shape for x in actions if x.shape and x.shape.type == "arrow")
    assert arrow.label_x is not None and arrow.label_y is not None
    on_route = any(
        min(ax, bx) - 1 <= arrow.label_x <= max(ax, bx) + 1
        and min(ay, by) - 1 <= arrow.label_y <= max(ay, by) + 1
        for (ax, ay), (bx, by) in _segments(arrow.points)
    )
    assert on_route


def test_grouped_layout_routes_clear_of_foreign_panels():
    # The fixture that used to produce through-panel arrows: cross-group edge from a
    # top panel to a bottom one must route around the panel(s) between them.
    plan = DiagramPlan(
        nodes=[
            PlanNode(id="a1", label="A1", group="g1"),
            PlanNode(id="a2", label="A2", group="g1"),
            PlanNode(id="b1", label="B1", group="g2"),
            PlanNode(id="c1", label="C1", group="g3"),
        ],
        edges=[
            PlanEdge(source="a1", target="a2"),
            PlanEdge(source="a2", target="b1"),
            PlanEdge(source="a1", target="c1", label="skip"),  # jumps past g2
        ],
        groups=[
            PlanGroup(id="g1", label="1. One"),
            PlanGroup(id="g2", label="2. Two"),
            PlanGroup(id="g3", label="3. Three"),
        ],
    )
    actions = route_arrows(build_graph_actions(plan))
    assert not any(i.kind == "arrow_crossing" for i in analyze_geometry(actions).issues)


def test_unroutable_arrow_falls_back_without_points():
    # Arrow bound to a container (not a box) — the router leaves it alone.
    actions = route_arrows(
        [
            AgentAction(
                type="create", shape=Shape(id="g", type="container", x=0, y=0, w=400, h=300)
            ),
            _box("a", 600, 0),
            _arrow("e", "a", "g"),
        ]
    )
    arrow = next(x.shape for x in actions if x.shape and x.shape.type == "arrow")
    assert arrow.points is None
