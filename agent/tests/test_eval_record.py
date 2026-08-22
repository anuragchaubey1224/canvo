"""Phase 01 — that a run comes out as a row, and always the same row.

The record's field set is a contract: rows written today get read back months from now,
so a rename is a silent data loss and a dropped field is a metric that stops existing.
The snapshot test below is what makes that break loudly.

The rest is arithmetic on signals the pipeline already produces. It is worth testing
because a metrics module that miscounts is worse than no metrics — it looks authoritative.
"""

from __future__ import annotations

from app.eval import RunRecord, record_from_run
from app.usage import PRICES, UsageMeter, price_of

# --- the contract -------------------------------------------------------------------------

EXPECTED_FIELDS = {
    "outcome",
    "input_kind",
    "intent",
    "nodes",
    "edges",
    "groups",
    "shapes",
    "components_specified",
    "assumptions",
    "degraded",
    "degraded_reason",
    "repairs",
    "issues",
    "blocking_issues",
    "refines",
    "first_pass_clean",
    "ops_proposed",
    "ops_applied",
    "ops_rejected",
    "input_tokens",
    "output_tokens",
    "cost_usd",
    "cost_known",
    "stage_ms",
    "total_ms",
}


def test_the_record_shape_is_pinned():
    """Adding a field is fine — update this set. Renaming or dropping one is not: every
    row already written uses the old name, and nothing will tell you."""
    assert set(RunRecord("completed", "text", "create").as_dict()) == EXPECTED_FIELDS


def test_a_record_is_json_serialisable():
    """It is stored as JSON on the run row, so anything unserialisable is a runtime
    failure at the end of a successful generation — the worst possible time."""
    import json

    record = record_from_run({"input_kind": "sql"}, outcome="completed")
    json.loads(json.dumps(record.as_dict()))


# --- deriving the row ----------------------------------------------------------------------


def _report(**over):
    base = {
        "nodes": 8,
        "edges": 7,
        "groups": 3,
        "issues": [],
        "fixes": [],
        "degraded": "",
        "intent": "create",
        "applied": [],
        "rejected": [],
    }
    base.update(over)
    return base


def test_counts_come_from_the_plan_report():
    record = record_from_run(
        {"input_kind": "text", "plan_report": _report()}, outcome="completed", shapes=16
    )
    assert (record.nodes, record.edges, record.groups, record.shapes) == (8, 7, 3, 16)
    assert record.intent == "create"


def test_a_stage_that_never_ran_is_none_not_zero():
    """The difference between "no overlaps" and "we never looked" is the whole point."""
    record = record_from_run({"input_kind": "text"}, outcome="failed")
    assert record.nodes is None
    assert record.first_pass_clean is None
    assert record.ops_applied is None


def test_issue_kinds_are_counted_across_validator_and_critic():
    state = {
        "plan_report": _report(
            issues=[
                {"kind": "missing_components", "severity": "error"},
                {"kind": "thin_phase", "severity": "warning"},
            ]
        )
    }
    passes = [
        {"has_issues": True, "issues": [{"kind": "overlap"}, {"kind": "overlap"}]},
        {"has_issues": False, "issues": []},
    ]
    record = record_from_run(state, outcome="completed", passes=passes)

    assert record.issues == {"missing_components": 1, "thin_phase": 1, "overlap": 2}
    assert record.issue_count == 4
    assert record.blocking_issues == 1, "only severity=error blocks"


def test_first_pass_clean_reads_the_first_pass_only():
    """Later passes only report on a layout that has already been widened, so they say
    nothing about whether the composition was right unaided."""
    dirty_then_clean = [
        {"has_issues": True, "issues": []},
        {"has_issues": False, "issues": []},
    ]
    dirty = record_from_run({}, outcome="completed", passes=dirty_then_clean)
    assert dirty.first_pass_clean is False

    clean = [{"has_issues": False, "issues": []}]
    assert record_from_run({}, outcome="completed", passes=clean).first_pass_clean is True


def test_refines_exclude_the_first_draw():
    """`iterations` counts drawer visits. Drawing once is not a refine."""
    assert record_from_run({"iterations": 1}, outcome="completed").refines == 0
    assert record_from_run({"iterations": 3}, outcome="completed").refines == 2
    assert record_from_run({}, outcome="failed").refines == 0


def test_degradation_is_recorded_with_its_reason():
    record = record_from_run(
        {"plan_report": _report(degraded="planner returned nothing; used the direct path")},
        outcome="completed",
    )
    assert record.degraded is True
    assert "direct path" in record.degraded_reason


def test_repairs_measures_how_much_the_raw_output_needed_fixing():
    record = record_from_run(
        {"plan_report": _report(fixes=["dropped a duplicate node", "re-pointed an edge"])},
        outcome="completed",
    )
    assert record.repairs == 2


def test_edit_ops_are_counted_only_on_an_edit():
    edit = record_from_run(
        {"plan_report": _report(intent="edit", applied=["added redis"], rejected=["unknown node"])},
        outcome="completed",
    )
    assert (edit.ops_proposed, edit.ops_applied, edit.ops_rejected) == (2, 1, 1)

    create = record_from_run({"plan_report": _report()}, outcome="completed")
    assert create.ops_proposed is None, "a create proposes no ops; zero would be a lie"


def test_a_question_is_its_own_intent():
    record = record_from_run({"answered": True}, outcome="completed")
    assert record.intent == "answer"


def test_stage_timings_are_carried_through_rounded():
    record = record_from_run(
        {},
        outcome="completed",
        stage_ms={"specifier": 1234.5678, "planner": 900.1},
        total_ms=2200.987,
    )
    assert record.stage_ms == {"specifier": 1234.6, "planner": 900.1}
    assert record.total_ms == 2201.0


# --- cost -----------------------------------------------------------------------------------


class _FakeHandler:
    """Stands in for LangChain's collector, so these tests need no model."""

    def __init__(self, usage):
        self.usage_metadata = usage


def _meter(usage):
    meter = UsageMeter()
    meter._handler = _FakeHandler(usage)  # type: ignore[assignment]
    return meter


def test_cost_is_derived_from_tokens_and_the_price_table():
    model = "google/gemini-3.7-flash"
    per_in, per_out = PRICES[model]
    meter = _meter({model: {"input_tokens": 1_000_000, "output_tokens": 1_000_000}})
    meter.collect()

    assert meter.input_tokens == 1_000_000
    assert meter.cost_usd == round(per_in + per_out, 6)
    assert meter.cost_known is True


def test_an_unpriced_model_still_counts_its_tokens():
    """A confident $0.00 for a model we have no price for would be worse than admitting
    the figure is incomplete."""
    meter = _meter({"some/unlisted-model": {"input_tokens": 500, "output_tokens": 200}})
    meter.collect()

    assert meter.total_tokens == 700
    assert meter.cost_known is False
    assert meter.unpriced_models == ["some/unlisted-model"]


def test_pricing_matches_on_the_model_tail():
    """Gateways prefix the vendor; a routing change must not silently drop pricing."""
    assert price_of("openrouter/google/gemini-3.7-flash") == PRICES["google/gemini-3.7-flash"]
    assert price_of("nothing/like/this") is None


def test_usage_lands_on_the_record():
    meter = _meter({"google/gemini-3.7-flash": {"input_tokens": 2000, "output_tokens": 500}})
    record = record_from_run({}, outcome="completed", meter=meter)

    assert record.input_tokens == 2000
    assert record.output_tokens == 500
    assert record.cost_usd > 0
    assert record.cost_known is True


def test_no_meter_means_zero_not_a_crash():
    """Plenty of runs have no model in them at all — SQL and OpenAPI go straight through."""
    record = record_from_run({"input_kind": "sql"}, outcome="completed")
    assert (record.input_tokens, record.cost_usd) == (0, 0.0)
    assert record.cost_known is True
