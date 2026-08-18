"""Composition — panels justified into a grid inside a frame (deterministic, no LLM)."""

from __future__ import annotations

from app.graph.compose import FRAME_PAD, Cell, choose_grid, compose
from app.graph.critique import analyze_geometry
from app.graph.layout import build_graph_actions
from app.graph.planner_llm import DiagramPlan, PlanEdge, PlanGroup, PlanNode
from app.graph.route import route_arrows


def _plan(sizes: list[int], *, link_groups: bool = True) -> DiagramPlan:
    """A plan with one phase per entry in `sizes`, each a chain of that many nodes."""
    nodes, edges, groups = [], [], []
    for g, count in enumerate(sizes, 1):
        groups.append(PlanGroup(id=f"g{g}", label=f"{g}. Phase {g}"))
        for n in range(count):
            nodes.append(PlanNode(id=f"n{g}{n}", label=f"Node {g}{n}", group=f"g{g}"))
            if n:
                edges.append(PlanEdge(source=f"n{g}{n - 1}", target=f"n{g}{n}"))
        if g > 1 and link_groups:
            edges.append(PlanEdge(source=f"n{g - 1}0", target=f"n{g}0"))
    return DiagramPlan(title="Test Diagram", nodes=nodes, edges=edges, groups=groups)


def _shapes(actions, shape_type):
    return [a.shape for a in actions if a.shape and a.shape.type == shape_type]


def _rows(panels):
    rows: dict[int, list] = {}
    for p in panels:
        rows.setdefault(round(p.y), []).append(p)
    return [rows[y] for y in sorted(rows)]


def test_every_row_shares_one_height():
    panels = _shapes(build_graph_actions(_plan([4, 2, 3, 2])), "container")
    for row in _rows(panels):
        assert len({round(p.h) for p in row}) == 1


def test_the_frame_encloses_every_panel():
    actions = build_graph_actions(_plan([4, 2, 3]))
    frame = _shapes(actions, "frame")[0]
    assert frame.text == "Test Diagram"
    for p in _shapes(actions, "container"):
        assert frame.x <= p.x and p.x + p.w <= frame.x + frame.w
        assert frame.y <= p.y and p.y + p.h <= frame.y + frame.h
    # the padding band is what the router uses as an outer gutter — it must survive
    left = min(p.x for p in _shapes(actions, "container")) - frame.x
    assert left >= FRAME_PAD


def test_composition_stays_poster_shaped_not_a_smear():
    # The old greedy packer composed this exact shape at 5.9:1 with a half-empty row.
    frame = _shapes(build_graph_actions(_plan([5, 4, 1, 3])), "frame")[0]
    assert 0.7 < frame.w / frame.h < 2.6


def test_narrow_panels_share_rows_instead_of_stacking():
    panels = _shapes(build_graph_actions(_plan([1, 1, 1, 1])), "container")
    assert len(_rows(panels)) < len(panels)


def test_a_lone_panel_is_not_stretched_across_the_whole_grid():
    actions = build_graph_actions(_plan([4, 4, 1]))
    panels = _shapes(actions, "container")
    lone = _rows(panels)[-1]
    assert len(lone) == 1
    assert lone[0].w < max(p.w for p in panels)  # capped, and centred rather than justified


def test_a_group_with_no_internal_flow_lays_out_as_a_row():
    # The reference's "Token Anatomy" lane: header / payload / signature, no arrows.
    plan = DiagramPlan(
        nodes=[
            PlanNode(id="a", label="Start", group="g1"),
            PlanNode(id="h", label="Header", group="g2"),
            PlanNode(id="p", label="Payload", group="g2"),
            PlanNode(id="s", label="Signature", group="g2"),
        ],
        edges=[PlanEdge(source="a", target="h")],
        groups=[PlanGroup(id="g1", label="1. One"), PlanGroup(id="g2", label="2. Anatomy")],
    )
    cards = [s for s in _shapes(build_graph_actions(plan), "geo") if s.id != "n-a"]
    assert len({round(c.y) for c in cards}) == 1  # one row, not a stacked column
    assert len({round(c.x) for c in cards}) == 3


def test_a_default_layout_reports_no_crowding():
    # Regression: the Critic's clearance bar once exceeded the layout's own tightest gap,
    # so every grouped diagram reported a phantom overlap and got force-widened 1.5x.
    for sizes in ([5, 4, 1, 3], [3, 3, 3], [2, 5], [1, 1, 1, 1]):
        actions = route_arrows(build_graph_actions(_plan(sizes), gap_scale=1.0))
        errors = [i for i in analyze_geometry(actions).issues if i.severity == "error"]
        assert not errors, f"{sizes}: {[i.message for i in errors]}"


def test_grid_is_pinned_so_fitting_cannot_move_the_columns():
    cells = [Cell(key=f"c{i}", w=w, h=200) for i, w in enumerate((1400, 900, 600))]
    grid = choose_grid(cells)
    comp = compose(cells, grid=grid)
    assert comp.grid == grid
    assert comp.grid.column_width * comp.grid.columns <= comp.grid.content_width
