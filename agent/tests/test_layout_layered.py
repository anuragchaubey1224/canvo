"""Layered layout + grouped containers (deterministic, no network/LLM)."""

from __future__ import annotations

from app.graph.critique import analyze_geometry
from app.graph.layout import build_graph_actions
from app.graph.planner_llm import DiagramPlan, PlanEdge, PlanGroup, PlanNode


def _errors(actions):  # hard geometry errors; advisory warnings (crossings/labels) excluded
    return [i for i in analyze_geometry(actions).issues if i.severity == "error"]


def _shapes(actions, shape_type):
    return [a.shape for a in actions if a.shape and a.shape.type == shape_type]


def _by_id(actions):
    return {a.shape.id: a.shape for a in actions if a.shape}


def _chain_plan() -> DiagramPlan:
    return DiagramPlan(
        nodes=[
            PlanNode(id="client", label="Client", kind="client"),
            PlanNode(id="auth", label="Auth Service", kind="service", subtitle="POST /auth/login"),
            PlanNode(id="db", label="User Store", kind="datastore"),
        ],
        edges=[
            PlanEdge(source="client", target="auth", label="credentials"),
            PlanEdge(source="auth", target="db", label="verify"),
        ],
    )


def test_chain_flows_top_down():
    shapes = _by_id(build_graph_actions(_chain_plan()))
    assert shapes["n-client"].y < shapes["n-auth"].y < shapes["n-db"].y


def test_layered_layout_is_clean_and_carries_semantics():
    actions = build_graph_actions(_chain_plan())
    assert not _errors(actions)

    auth = _by_id(actions)["n-auth"]
    assert auth.kind == "service"
    assert auth.subtitle == "POST /auth/login"
    assert auth.color == "blue"  # kind-default color


def test_siblings_share_a_row():
    plan = DiagramPlan(
        nodes=[
            PlanNode(id="gw", label="Gateway"),
            PlanNode(id="svc-a", label="Service A"),
            PlanNode(id="svc-b", label="Service B"),
        ],
        edges=[
            PlanEdge(source="gw", target="svc-a"),
            PlanEdge(source="gw", target="svc-b"),
        ],
    )
    shapes = _by_id(build_graph_actions(plan))
    assert shapes["n-svc-a"].y == shapes["n-svc-b"].y  # same rank → same row
    assert shapes["n-svc-a"].x != shapes["n-svc-b"].x
    assert shapes["n-gw"].y < shapes["n-svc-a"].y


def test_decision_nodes_get_diamond_room():
    plan = DiagramPlan(
        nodes=[
            PlanNode(id="check", label="Token valid?", kind="decision"),
            PlanNode(id="ok", label="Resource API", kind="service"),
        ],
        edges=[PlanEdge(source="check", target="ok", label="valid")],
    )
    shapes = _by_id(build_graph_actions(plan))
    assert shapes["n-check"].h > shapes["n-ok"].h
    assert shapes["n-check"].kind == "decision"


def _grouped_plan() -> DiagramPlan:
    return DiagramPlan(
        nodes=[
            PlanNode(id="client", label="Client App", kind="client", group="issuance"),
            PlanNode(id="auth", label="Auth Service", kind="service", group="issuance"),
            PlanNode(id="gateway", label="API Gateway", kind="service", group="verify"),
            PlanNode(id="check", label="Signature valid?", kind="decision", group="verify"),
        ],
        edges=[
            PlanEdge(source="client", target="auth", label="credentials"),
            PlanEdge(source="auth", target="gateway", label="token"),  # cross-group
            PlanEdge(source="gateway", target="check"),
        ],
        groups=[
            PlanGroup(id="issuance", label="1. Login & Token Issuance"),
            PlanGroup(id="verify", label="2. Request Verification"),
        ],
    )


def test_groups_become_containers_with_members_inside():
    actions = build_graph_actions(_grouped_plan())
    containers = {c.id: c for c in _shapes(actions, "container")}
    assert set(containers) == {"g-issuance", "g-verify"}
    assert containers["g-issuance"].text == "1. Login & Token Issuance"
    assert containers["g-issuance"].color  # accent assigned

    for shape in _shapes(actions, "geo"):
        assert shape.parent_id in containers
        c = containers[shape.parent_id]
        assert c.x <= shape.x and shape.x + shape.w <= c.x + c.w
        assert c.y <= shape.y and shape.y + shape.h <= c.y + c.h

    # geometry critic agrees: no overlaps, no overflow, no dangling arrows
    assert not _errors(actions)


def test_containers_stream_before_their_members():
    actions = build_graph_actions(_grouped_plan())
    kinds = [a.shape.type for a in actions if a.shape]
    assert kinds.index("container") < kinds.index("geo")  # z-order via creation order


def test_cross_group_edge_stays_bound():
    actions = build_graph_actions(_grouped_plan())
    arrows = _shapes(actions, "arrow")
    assert any(x.from_id == "n-auth" and x.to_id == "n-gateway" for x in arrows)


def test_group_rank_orders_containers_in_reading_order():
    actions = build_graph_actions(_grouped_plan())
    containers = {c.id: c for c in _shapes(actions, "container")}
    # issuance feeds verify → issuance comes first in reading order (above, or
    # left of it when the packer put both panels on one grid row)
    a, b = containers["g-issuance"], containers["g-verify"]
    assert a.y < b.y or (a.y == b.y and a.x < b.x)


def test_members_flow_left_to_right_inside_panels():
    shapes = _by_id(build_graph_actions(_grouped_plan()))
    # client → auth chain inside the issuance panel runs horizontally, not stacked
    assert shapes["n-client"].x < shapes["n-auth"].x


def test_linear_stage_chain_packs_into_a_grid_not_a_column():
    # 4 single-node groups chained 1→2→3→4: naive rank-rows would stack them in one
    # tall column; the packer must wrap them into more than one panel per row.
    plan = DiagramPlan(
        nodes=[PlanNode(id=f"s{i}", label=f"Step {i}", group=f"g{i}") for i in range(4)],
        edges=[PlanEdge(source=f"s{i}", target=f"s{i + 1}") for i in range(3)],
        groups=[PlanGroup(id=f"g{i}", label=f"{i + 1}. Stage {i}") for i in range(4)],
    )
    containers = _shapes(build_graph_actions(plan), "container")
    distinct_rows = {c.y for c in containers}
    assert len(distinct_rows) < len(containers)  # at least one row holds 2+ panels
    assert not _errors(build_graph_actions(plan))


def test_edge_to_unknown_node_is_dropped_not_dangling():
    plan = _chain_plan()
    plan.edges.append(PlanEdge(source="auth", target="ghost"))
    actions = build_graph_actions(plan)
    assert not any(i.kind == "dangling_arrow" for i in analyze_geometry(actions).issues)


def test_loose_nodes_rank_individually_around_groups():
    # A loose Start feeding group 1 reads BEFORE it; a loose End fed by the last group
    # reads AFTER it (regression: bunching loose nodes into one shared trailing row).
    plan = _grouped_plan()
    plan.nodes.append(PlanNode(id="start", label="Start", kind="start"))
    plan.nodes.append(PlanNode(id="end", label="End", kind="end"))
    plan.edges.append(PlanEdge(source="start", target="client"))
    plan.edges.append(PlanEdge(source="check", target="end"))

    actions = build_graph_actions(plan)
    shapes = _by_id(actions)
    containers = {c.id: c for c in _shapes(actions, "container")}

    def reads_before(a, b):  # same row (vertical ranges overlap) → by x, else by y
        same_row = a.y < b.y + b.h and b.y < a.y + a.h
        return a.x < b.x if same_row else a.y < b.y

    assert reads_before(shapes["n-start"], containers["g-issuance"])
    assert reads_before(containers["g-verify"], shapes["n-end"])
    assert shapes["n-start"].parent_id is None
    assert not _errors(actions)


def test_gap_scale_widens_grouped_layout():
    base = build_graph_actions(_grouped_plan(), gap_scale=1.0)
    wide = build_graph_actions(_grouped_plan(), gap_scale=1.5)
    base_c = {c.id: c for c in _shapes(base, "container")}
    wide_c = {c.id: c for c in _shapes(wide, "container")}
    # wider member gaps → the panel itself must grow
    assert wide_c["g-issuance"].w > base_c["g-issuance"].w
