"""Phase 01 — the per-run cost cap actually fires.

`guardrails.within_budget()` was written and never called. It now gates the two
discretionary model calls left in a run: the planner's one repair pass and the vision
Critic. A capped run still returns a diagram — it just goes without the extras — and is
marked `budget_capped` so it can never be mistaken for a first-pass-clean one.

Fully offline: a `UsageMeter` is handed a fake usage total, so "this run has spent $X" is
established with no model in the path.
"""

from __future__ import annotations

import asyncio

from app import guardrails
from app.graph import nodes
from app.graph.build import _should_refine
from app.graph.planner_llm import DiagramPlan, PlanNode
from app.graph.validate_plan import PlanIssue, PlanReport
from app.usage import UsageMeter


class _FakeHandler:
    def __init__(self, usage: dict):
        self.usage_metadata = usage


def _meter_that_spent(input_tokens: int) -> UsageMeter:
    """A meter reporting a priced model (`google/gemini-3.7-flash`, $0.30/M input) having
    burned `input_tokens`. 1_000_000 → $0.30 of real, accountable spend."""
    meter = UsageMeter()
    meter._handler = _FakeHandler(  # type: ignore[assignment]
        {"google/gemini-3.7-flash": {"input_tokens": input_tokens, "output_tokens": 0}}
    )
    return meter


# --- the policy -------------------------------------------------------------------------


def test_within_budget_respects_the_env_cap(monkeypatch):
    monkeypatch.setenv("MAX_RUN_COST_USD", "0.10")
    assert guardrails.within_budget(0.05)
    assert not guardrails.within_budget(0.10)  # at the cap counts as spent
    assert not guardrails.within_budget(0.25)


def test_a_zero_cap_disables_the_check(monkeypatch):
    """The documented escape hatch, matching the quota limits' `0` convention."""
    monkeypatch.setenv("MAX_RUN_COST_USD", "0")
    assert guardrails.within_budget(9999.0)


def test_a_broken_cap_falls_back_to_the_default_not_to_unlimited(monkeypatch):
    monkeypatch.setenv("MAX_RUN_COST_USD", "lots please")
    assert guardrails.max_run_cost_usd() == guardrails.DEFAULT_MAX_RUN_COST_USD
    monkeypatch.setenv("MAX_RUN_COST_USD", "-1")
    assert guardrails.max_run_cost_usd() == 0.0  # clamped; 0 is the explicit "off"


# --- the refine router -----------------------------------------------------------------


def test_should_refine_stops_a_capped_run():
    state = {"budget_capped": True, "critique": {"needs_refine": True}, "iterations": 1}
    assert _should_refine(state) == "done"


def test_should_refine_still_loops_when_under_budget():
    state = {"critique": {"needs_refine": True}, "iterations": 1}
    assert _should_refine(state) == "refine"


# --- the vision pass -----------------------------------------------------------------


def test_over_budget_skips_the_vision_pass(monkeypatch):
    monkeypatch.setenv("MAX_RUN_COST_USD", "0.01")
    called: list[int] = []

    async def fake_vision(*_a, **_k):
        called.append(1)
        raise AssertionError("the vision pass ran while the run was over its cost cap")

    monkeypatch.setattr(nodes, "critique_image", fake_vision)

    state = {
        "actions": [],
        "iterations": 0,
        "vision_enabled": True,
        "layout_params": {"gap_scale": 1.0},
        "meter": _meter_that_spent(1_000_000),  # $0.30, far over the $0.01 cap
    }
    out = asyncio.run(nodes.critic(state))

    assert not called
    assert out["budget_capped"] is True


def test_under_budget_still_runs_the_vision_pass(monkeypatch):
    monkeypatch.setenv("MAX_RUN_COST_USD", "0.50")
    called: list[int] = []

    async def fake_vision(*_a, **_k):
        called.append(1)
        return None

    monkeypatch.setattr(nodes, "critique_image", fake_vision)

    state = {
        "actions": [],
        "iterations": 0,
        "vision_enabled": True,
        "layout_params": {"gap_scale": 1.0},
        "meter": _meter_that_spent(1_000),  # $0.0003, far under
    }
    out = asyncio.run(nodes.critic(state))

    assert called == [1]
    assert "budget_capped" not in out


def test_no_meter_means_no_cap(monkeypatch):
    """A test that stubs the model has no meter; the cap must not fire on `None`."""
    monkeypatch.setenv("MAX_RUN_COST_USD", "0.01")
    called: list[int] = []

    async def fake_vision(*_a, **_k):
        called.append(1)
        return None

    monkeypatch.setattr(nodes, "critique_image", fake_vision)
    state = {"actions": [], "iterations": 0, "vision_enabled": True, "layout_params": {}}
    out = asyncio.run(nodes.critic(state))

    assert called == [1]
    assert "budget_capped" not in out


# --- the plan repair pass -----------------------------------------------------------------


def test_over_budget_skips_the_plan_repair(monkeypatch):
    monkeypatch.setenv("MAX_RUN_COST_USD", "0.01")

    blocking = PlanReport(issues=[PlanIssue("missing_components", "error", "dropped 'redis'")])
    monkeypatch.setattr(nodes, "validate", lambda *_a, **_k: blocking)

    async def fake_plan_from_text(*_a, **_k):
        return DiagramPlan(nodes=[PlanNode(id="a", label="A")], edges=[], groups=[])

    repair_calls: list[int] = []

    async def fake_refine(*_a, **_k):
        repair_calls.append(1)
        raise AssertionError("the plan repair pass ran while over the cost cap")

    monkeypatch.setattr(nodes, "plan_from_text", fake_plan_from_text)
    monkeypatch.setattr(nodes, "refine_plan", fake_refine)

    state = {
        "payload": "a description long enough to plan from",
        "input_kind": "text",
        "spec": None,
        "meter": _meter_that_spent(1_000_000),
    }
    out = asyncio.run(nodes.planner(state))

    assert not repair_calls
    assert out["budget_capped"] is True
    # the un-repaired plan still draws, with its issues on the record
    assert out["llm_plan"].nodes
    assert any(i["kind"] == "missing_components" for i in out["plan_report"]["issues"])


def test_under_budget_still_runs_the_plan_repair(monkeypatch):
    monkeypatch.setenv("MAX_RUN_COST_USD", "0.50")

    blocking = PlanReport(issues=[PlanIssue("missing_components", "error", "dropped 'redis'")])
    clean = PlanReport(issues=[])
    reports = iter([blocking, clean])
    monkeypatch.setattr(nodes, "validate", lambda *_a, **_k: next(reports, clean))

    async def fake_plan_from_text(*_a, **_k):
        return DiagramPlan(nodes=[PlanNode(id="a", label="A")], edges=[], groups=[])

    repair_calls: list[int] = []

    async def fake_refine(*_a, **_k):
        repair_calls.append(1)
        return DiagramPlan(
            nodes=[PlanNode(id="a", label="A"), PlanNode(id="redis", label="Redis")],
            edges=[],
            groups=[],
        )

    monkeypatch.setattr(nodes, "plan_from_text", fake_plan_from_text)
    monkeypatch.setattr(nodes, "refine_plan", fake_refine)

    state = {
        "payload": "a description long enough to plan from",
        "input_kind": "text",
        "spec": None,
        "meter": _meter_that_spent(1_000),
    }
    out = asyncio.run(nodes.planner(state))

    assert repair_calls == [1]
    assert "budget_capped" not in out
    assert out["plan_report"]["repaired"] is True
