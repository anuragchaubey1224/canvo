"""Tier 1 — the deterministic golden set. See EVAL-PLAN.md §4, §7 (phase 02).

Every case here runs with no model in the path: SQL/OpenAPI parsing, edit-op application
against a fixed plan, and composition/routing against frozen plan fixtures. The one LLM
call each path would otherwise make is monkeypatched to a frozen return value (see
`harness.py`) — the rest is real production code. Runs in seconds, with no network; wire
this file into CI on every commit.

`test_tier1_aggregate_report` must run last: it reads `_RECORDS`, which the four
parametrized functions above it populate as they run. pytest collects a module's tests in
source order and this suite has no xdist/randomly plugin configured (see pyproject.toml),
so that ordering is safe — and `test_tier1_aggregate_report` asserts the count as a
tripwire in case that ever stops being true.
"""

from __future__ import annotations

import pytest
from harness import check_properties, load_cases, run_case

from app.eval.metrics import aggregate
from app.eval.record import RunRecord

SQL_CASES = load_cases("sql")
OPENAPI_CASES = load_cases("openapi")
EDIT_CASES = load_cases("edit")
CREATE_CASES = load_cases("create")
_ALL_CASES = {c["id"]: c for c in SQL_CASES + OPENAPI_CASES + EDIT_CASES + CREATE_CASES}
_TOTAL_CASES = len(_ALL_CASES)

# Populated by the four parametrized test functions below; read by the aggregate report.
_RECORDS: dict[str, RunRecord] = {}


def _run_and_check(case: dict, monkeypatch) -> None:
    state, record = run_case(case, monkeypatch)
    _RECORDS[case["id"]] = record
    violations = check_properties(case, state)
    assert not violations, f"{case['id']}: " + "; ".join(violations)


@pytest.mark.parametrize("case", SQL_CASES, ids=[c["id"] for c in SQL_CASES])
def test_sql_case(case, monkeypatch):
    _run_and_check(case, monkeypatch)


@pytest.mark.parametrize("case", OPENAPI_CASES, ids=[c["id"] for c in OPENAPI_CASES])
def test_openapi_case(case, monkeypatch):
    _run_and_check(case, monkeypatch)


@pytest.mark.parametrize("case", EDIT_CASES, ids=[c["id"] for c in EDIT_CASES])
def test_edit_case(case, monkeypatch):
    _run_and_check(case, monkeypatch)


@pytest.mark.parametrize("case", CREATE_CASES, ids=[c["id"] for c in CREATE_CASES])
def test_create_case(case, monkeypatch):
    _run_and_check(case, monkeypatch)


def test_tier1_aggregate_report():
    """Definition of done (EVAL-PLAN.md §8): this produces the aggregate report and fails
    on the hard gates — any degraded run, or structural validity below 100%."""
    assert len(_RECORDS) == _TOTAL_CASES, (
        "not every golden case ran before the aggregate — did the module run out of order, "
        "or get filtered with -k? Run the whole file: pytest tests/eval/test_tier1.py"
    )
    report = aggregate(_RECORDS)
    print(f"\n{report.render()}")
    assert not report.degraded_cases, f"degraded run(s) in the golden set: {report.degraded_cases}"

    # A handful of `create` cases deliberately feed the validator bad content to prove it's
    # caught (create-missing-components-flagged.json, create-decision-needs-two-branches.json,
    # create-isolated-node-flagged.json) — their own `blocking_issues_max` already budgets
    # that in, and `check_properties` above confirmed the right issue kind actually fired.
    # The 100% gate applies to every other case: a plan built from good input must come out
    # with zero blocking validator issues.
    unexpected_invalid = [
        cid
        for cid in report.invalid_cases
        if _ALL_CASES[cid].get("expect", {}).get("blocking_issues_max", 0) == 0
    ]
    assert not unexpected_invalid, (
        f"structural validity below 100% on case(s) with no budget for it: {unexpected_invalid}"
    )
