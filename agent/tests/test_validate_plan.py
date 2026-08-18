"""Plan validator — structural sanitize + content checks (deterministic, no LLM)."""

from __future__ import annotations

from app.graph.planner_llm import DiagramPlan, PlanEdge, PlanGroup, PlanNode
from app.graph.spec_llm import parse_spec
from app.graph.validate_plan import sanitize, validate


def _plan(**kw) -> DiagramPlan:
    return DiagramPlan(**kw)


def test_sanitize_drops_dangling_self_and_duplicate_edges():
    plan = _plan(
        nodes=[PlanNode(id="a", label="A"), PlanNode(id="b", label="B")],
        edges=[
            PlanEdge(source="a", target="b"),
            PlanEdge(source="a", target="b"),  # duplicate
            PlanEdge(source="a", target="ghost"),  # dangling
            PlanEdge(source="b", target="b"),  # self-loop
        ],
    )
    fixes = sanitize(plan)
    assert [(e.source, e.target) for e in plan.edges] == [("a", "b")]
    assert len(fixes) == 3


def test_sanitize_clears_unknown_group_refs_and_drops_empty_groups():
    plan = _plan(
        nodes=[PlanNode(id="a", label="A", group="ghost"), PlanNode(id="b", label="B", group="g1")],
        edges=[PlanEdge(source="a", target="b")],
        groups=[PlanGroup(id="g1", label="1. One"), PlanGroup(id="g2", label="2. Empty")],
    )
    sanitize(plan)
    assert plan.nodes[0].group is None
    assert [g.id for g in plan.groups] == ["g1"]


def test_decision_with_one_branch_is_blocking():
    plan = _plan(
        nodes=[
            PlanNode(id="a", label="A"),
            PlanNode(id="d", label="Valid?", kind="decision"),
            PlanNode(id="b", label="B"),
        ],
        edges=[PlanEdge(source="a", target="d"), PlanEdge(source="d", target="b", label="yes")],
    )
    sanitize(plan)
    report = validate(plan)
    assert [i.kind for i in report.blocking] == ["single_branch"]


def test_isolated_node_is_blocking():
    plan = _plan(
        nodes=[
            PlanNode(id="a", label="A"),
            PlanNode(id="b", label="B"),
            PlanNode(id="x", label="X"),
        ],
        edges=[PlanEdge(source="a", target="b")],
    )
    sanitize(plan)
    assert any(i.kind == "isolated_node" for i in validate(plan).blocking)


def test_a_reference_panel_is_not_a_pile_of_isolated_nodes():
    # The reference diagram's "Token Anatomy" lane holds three cards with no arrows at
    # all. Flagging those would spend a repair call inventing edges that shouldn't exist.
    plan = _plan(
        nodes=[
            PlanNode(id="a", label="Start", group="g1"),
            PlanNode(id="b", label="Next", group="g1"),
            PlanNode(id="h", label="Header", group="g2"),
            PlanNode(id="p", label="Payload", group="g2"),
            PlanNode(id="s", label="Signature", group="g2"),
        ],
        edges=[PlanEdge(source="a", target="b")],
        groups=[PlanGroup(id="g1", label="1. Flow"), PlanGroup(id="g2", label="2. Anatomy")],
    )
    sanitize(plan)
    assert not [i for i in validate(plan).blocking if i.kind == "isolated_node"]


def test_a_node_stranded_inside_a_flowing_group_is_still_blocking():
    plan = _plan(
        nodes=[
            PlanNode(id="a", label="A", group="g1"),
            PlanNode(id="b", label="B", group="g1"),
            PlanNode(id="x", label="Orphan", group="g1"),
        ],
        edges=[PlanEdge(source="a", target="b")],
        groups=[PlanGroup(id="g1", label="1. Flow")],
    )
    sanitize(plan)
    assert any(i.kind == "isolated_node" for i in validate(plan).blocking)


def test_dropped_spec_components_are_blocking():
    spec = parse_spec(
        "COMPONENTS:\n- Client App (client)\n- Auth Service (service)\n"
        "- User Database (datastore)\n- API Gateway (service)\n"
        "FLOW:\n1. Client App -> Auth Service: credentials\n"
    )
    plan = _plan(
        nodes=[
            PlanNode(id="client", label="Client App"),
            PlanNode(id="auth", label="Auth Service"),
        ],
        edges=[PlanEdge(source="client", target="auth")],
    )
    sanitize(plan)
    issue = next(i for i in validate(plan, spec).blocking if i.kind == "missing_components")
    assert "User Database" in issue.message and "API Gateway" in issue.message


def test_thin_coverage_against_the_spec_flow():
    spec = parse_spec(
        "COMPONENTS:\n- A (service)\n- B (service)\n"
        "FLOW:\n1. A -> B: x\n2. B -> A: y\n3. A -> B: z\n4. B -> A: w\n5. A -> B: v\n"
    )
    plan = _plan(
        nodes=[PlanNode(id="a", label="A"), PlanNode(id="b", label="B")],
        edges=[PlanEdge(source="a", target="b")],
    )
    sanitize(plan)
    assert any(i.kind == "thin_coverage" for i in validate(plan, spec).blocking)


def test_a_faithful_plan_is_clean():
    spec = parse_spec(
        "COMPONENTS:\n- Client App (client)\n- Auth Service (service)\n- Valid? (decision)\n"
        "FLOW:\n1. Client App -> Auth Service: credentials\n2. Auth Service -> Valid?: check\n"
        "PHASES:\n1. Login: Client App, Auth Service\n"
    )
    plan = _plan(
        nodes=[
            PlanNode(id="client", label="Client App", group="g1"),
            PlanNode(id="auth", label="Auth Service", group="g1"),
            PlanNode(id="valid", label="Valid?", kind="decision", group="g1"),
            PlanNode(id="ok", label="Issue Tokens", group="g1"),
            PlanNode(id="no", label="401 Unauthorized", group="g1"),
        ],
        edges=[
            PlanEdge(source="client", target="auth", label="credentials"),
            PlanEdge(source="auth", target="valid", label="check"),
            PlanEdge(source="valid", target="ok", label="yes"),
            PlanEdge(source="valid", target="no", label="no"),
        ],
        groups=[PlanGroup(id="g1", label="1. Login")],
    )
    sanitize(plan)
    assert validate(plan, spec).is_clean
