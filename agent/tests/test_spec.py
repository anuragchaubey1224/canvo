"""Spec Writer parsing — deterministic, no network/LLM."""

from __future__ import annotations

from app.graph.spec_llm import parse_spec, spec_to_plan

SPEC = """TITLE: JWT Authentication Workflow
TYPE: workflow
COMPONENTS:
- Client App (client) - browser or mobile
- Auth Service (service) - POST /auth/login
- User Database (datastore) - credential lookup
- Valid? (decision) - -
FLOW:
1. Client App -> Auth Service: credentials
2. Auth Service -> User Database: lookup
3. Valid? -> Issue Tokens: yes
4. Valid? -> 401 Unauthorized: no
PHASES:
1. Login & Token Issuance: Client App, Auth Service
2. Verification: Valid?
ASSUMPTIONS:
- Access tokens are short-lived; refresh tokens are long-lived.
- The token store is not specified, so it is shown generically.
"""


def test_parses_every_section():
    spec = parse_spec(SPEC)
    assert spec.title == "JWT Authentication Workflow"
    assert spec.diagram_type == "workflow"
    assert spec.component_names == ["Client App", "Auth Service", "User Database", "Valid?"]
    assert len(spec.flow_steps) == 4
    assert len(spec.phases) == 2
    assert len(spec.assumptions) == 2
    assert spec.raw.startswith("TITLE:")


def test_component_line_splits_into_name_kind_and_detail():
    spec = parse_spec("COMPONENTS:\n- API Gateway (service) - verifies signature\n")
    assert spec.component_names == ["API Gateway"]
    assert spec.components[0].kind == "service"
    assert spec.components[0].detail == "verifies signature"


def test_a_placeholder_detail_is_dropped_not_rendered():
    spec = parse_spec("COMPONENTS:\n- Valid? (decision) - -\n")
    assert spec.components[0].detail is None


def test_an_unknown_kind_is_ignored_rather_than_passed_through():
    spec = parse_spec("COMPONENTS:\n- Thing (whatever) - detail\n")
    assert spec.components[0].kind is None and spec.components[0].name == "Thing"


def test_tolerates_markdown_decoration_and_stray_prose():
    spec = parse_spec(
        "Here is the spec.\n"
        "**TITLE:** Order Pipeline\n"
        "## COMPONENTS:\n"
        "* Checkout (client)\n"
        "* Payment (service)\n"
        "FLOW:\n"
        "1) Checkout -> Payment: charge\n"
    )
    assert spec.title == "Order Pipeline"
    assert spec.component_names == ["Checkout", "Payment"]
    assert spec.flow_steps == ["Checkout -> Payment: charge"]


def test_missing_sections_come_back_empty_not_broken():
    spec = parse_spec("TITLE: Bare\n")
    assert spec.title == "Bare"
    assert spec.components == [] and spec.assumptions == []


# --- spec_to_plan: the no-LLM fallback that runs when the planner call fails ---


def test_spec_alone_builds_a_real_diagram():
    plan = spec_to_plan(parse_spec(SPEC))
    assert plan is not None
    assert plan.title == "JWT Authentication Workflow"
    assert {n.label for n in plan.nodes} == {
        "Client App",
        "Auth Service",
        "User Database",
        "Valid?",
    }
    assert len(plan.edges) == 2  # only 2 of the 4 FLOW steps name known components
    assert [g.label for g in plan.groups] == ["1. Login & Token Issuance", "2. Verification"]


def test_the_fallback_carries_kinds_subtitles_and_edge_labels():
    plan = spec_to_plan(parse_spec(SPEC))
    auth = next(n for n in plan.nodes if n.label == "Auth Service")
    assert auth.kind == "service" and auth.subtitle == "POST /auth/login"
    assert next(n for n in plan.nodes if n.label == "Valid?").kind == "decision"
    assert any(e.label == "credentials" for e in plan.edges)


def test_the_fallback_assigns_phases_as_groups():
    plan = spec_to_plan(parse_spec(SPEC))
    client = next(n for n in plan.nodes if n.label == "Client App")
    assert client.group == "phase-1"


def test_flow_steps_may_abbreviate_a_component_name():
    spec = parse_spec(
        "COMPONENTS:\n- API Gateway (service)\n- Backend Service (service)\n"
        "FLOW:\n1. Gateway -> Backend Service: forward\n"
    )
    plan = spec_to_plan(spec)
    assert plan is not None and len(plan.edges) == 1
    assert plan.edges[0].source == "api-gateway"


def test_a_spec_with_no_usable_flow_yields_nothing_to_draw():
    assert spec_to_plan(parse_spec("COMPONENTS:\n- Only (service)\n")) is None
