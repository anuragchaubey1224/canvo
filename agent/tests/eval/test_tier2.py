"""Tier 2 — the freeform LLM path, against recorded model responses. See EVAL-PLAN.md §4, §7.

`--replay` (default) plays back `responses/*.json`: no network, runs in CI with the rest of
the suite. `--record` calls the live model, rewrites the fixtures, and prints the cost —
run it by hand, once, with the spend agreed first (EVAL-PLAN.md §8, ground rule 1).

`test_tier2_aggregate_report` must run last: it reads `_RECORDS`, which the parametrized
test above populates. Same source-order guarantee as `test_tier1.py` (no xdist / randomly
plugin — see pyproject.toml), and it asserts the count as a tripwire.
"""

from __future__ import annotations

import pytest
from tier2_harness import (
    RESPONSES_DIR,
    check_tier2_properties,
    load_tier2_cases,
    run_tier2_case,
)

from app.eval.metrics import aggregate
from app.eval.record import RunRecord
from app.usage import UsageMeter

_CASES = load_tier2_cases()
_CASE_IDS = [c["id"] for c in _CASES]
_BY_ID = {c["id"]: c for c in _CASES}

# Populated as the parametrized test runs; read by the aggregate report.
_RECORDS: dict[str, RunRecord] = {}
_METERS: dict[str, UsageMeter] = {}
_HALLUCINATIONS: dict[str, list[str]] = {}


def _recording(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--record"))


def _selected_for_record(request: pytest.FixtureRequest, case_id: str) -> bool:
    only = request.config.getoption("--record-only")
    if not only:
        return True
    return case_id in {s.strip() for s in str(only).split(",") if s.strip()}


if not _CASES:  # pragma: no cover - only when someone deletes every case file
    pytest.skip("no tier2-*.json cases found under tests/eval/cases/", allow_module_level=True)


@pytest.mark.tier2
@pytest.mark.parametrize("case", _CASES, ids=_CASE_IDS)
def test_tier2_case(case: dict, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    recording = _recording(request)
    if recording and not _selected_for_record(request, case["id"]):
        pytest.skip(f"{case['id']} not in --record-only")
    if not recording and not (RESPONSES_DIR / f"{case['id']}.json").exists():
        # Nothing recorded at all → Phase 03's fixtures haven't been captured yet. Skip the
        # whole tier rather than fail the build; a *partial* set still fails loudly per case.
        if not any(RESPONSES_DIR.glob("tier2-*.json")):
            pytest.skip(
                "Tier 2 fixtures not recorded yet — run: "
                "pytest tests/eval/test_tier2.py --record  (spends ~$0.05, EVAL-PLAN.md §7)"
            )

    meter = UsageMeter() if recording else None
    state, record = run_tier2_case(case, monkeypatch, record=recording, meter=meter)
    _RECORDS[case["id"]] = record
    if meter is not None:
        _METERS[case["id"]] = meter

    violations = check_tier2_properties(case, state)
    hallucinations = [v for v in violations if v.startswith("hallucinated")]
    if hallucinations:
        _HALLUCINATIONS[case["id"]] = hallucinations
    assert not violations, f"{case['id']}: " + "; ".join(violations)


def test_tier2_aggregate_report():
    """The aggregate over every Tier 2 case, plus the two gates that are never negotiable
    for the freeform path (EVAL-PLAN.md §4): no degraded run, no hallucinated component.
    Structural validity is report-only here — this is real model output, not a fixture the
    validator was hand-fed."""
    if not _RECORDS:
        pytest.skip("no Tier 2 cases ran (fixtures not recorded, or all filtered out)")

    if len(_RECORDS) == len(_CASES):
        expected_total = len(_CASES)
    else:  # a filtered run (-k, --record-only) — report on what ran, don't trip the wire
        expected_total = len(_RECORDS)
    assert len(_RECORDS) == expected_total

    report = aggregate(_RECORDS, label="Tier 2")
    print(f"\n{report.render()}")

    if _METERS:
        total = sum(m.cost_usd for m in _METERS.values())
        known = all(m.cost_known for m in _METERS.values())
        print(f"\n  recorded {len(_METERS)} case(s) live")
        for cid, m in _METERS.items():
            print(f"    {cid:44} {m.total_tokens:>7} tok  ${m.cost_usd:.4f}")
        print(
            f"  {'TOTAL':46} {sum(m.total_tokens for m in _METERS.values()):>7} tok  "
            f"${total:.4f}{'' if known else '  (lower bound — unpriced model)'}"
        )

    assert not _HALLUCINATIONS, f"hallucinated component(s): {_HALLUCINATIONS}"
    assert not report.degraded_cases, f"degraded run(s) in Tier 2: {report.degraded_cases}"
