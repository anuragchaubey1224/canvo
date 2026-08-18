"""Planner degradation — what the user gets when the LLM plan call fails (no network)."""

from __future__ import annotations

import asyncio

from app.graph import nodes
from app.graph.spec_llm import parse_spec, spec_to_plan

SPEC = parse_spec(
    """TITLE: Order Pipeline
TYPE: workflow
COMPONENTS:
- Checkout (client) - web
- Payment Service (service) - POST /pay
- Ledger (datastore) - -
FLOW:
1. Checkout -> Payment Service: charge
2. Payment Service -> Ledger: record
PHASES:
1. Purchase: Checkout, Payment Service
2. Settlement: Ledger
ASSUMPTIONS:
- Payments are card-only.
"""
)


def _run_planner(monkeypatch, *, plan_returns, spec=SPEC) -> dict:
    async def fake_plan(*_args, **_kwargs):
        return plan_returns

    monkeypatch.setattr(nodes, "plan_from_text", fake_plan)
    state = {"input_kind": "text", "payload": "draw an order pipeline", "spec": spec}
    return asyncio.run(nodes.planner(state))


def test_a_failed_planner_draws_the_spec_instead_of_a_stub(monkeypatch):
    # The failure this guards: a swallowed planner error used to leave a two-box
    # "Start → <first 24 chars of the prompt>" placeholder that read like a real answer.
    plan = _run_planner(monkeypatch, plan_returns=None)["llm_plan"]
    assert [n.label for n in plan.nodes] == ["Checkout", "Payment Service", "Ledger"]
    assert len(plan.edges) == 2
    assert [g.label for g in plan.groups] == ["1. Purchase", "2. Settlement"]
    assert "Start" not in {n.label for n in plan.nodes}


def test_the_fallback_is_reported_not_hidden(monkeypatch):
    report = _run_planner(monkeypatch, plan_returns=None)["plan_report"]
    assert report["degraded"]
    assert report["nodes"] == 3


def test_a_working_planner_reports_no_degradation(monkeypatch):
    report = _run_planner(monkeypatch, plan_returns=spec_to_plan(SPEC))["plan_report"]
    assert report["degraded"] == ""


def test_no_spec_and_no_planner_still_falls_back_to_the_stub(monkeypatch):
    # Without a spec there is nothing to draw from, so the placeholder is all that's left.
    out = _run_planner(monkeypatch, plan_returns=None, spec=None)
    assert out["plan"]["notes"].startswith("stub plan")
