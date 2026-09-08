"""One run of the graph, flattened into one row.

This is the join between what the pipeline already knows about itself and what a metrics
query needs. The validator and the critic raise typed issues on every run and the request
throws them away; everything below is a matter of keeping them in a shape that aggregates.

Two rules this module lives by:

  - **Derive, never estimate.** Every field comes from something the run actually
    produced. A count the run did not report is `None`, not zero — the difference between
    "no overlaps" and "we never looked" is the whole point of measuring.
  - **The shape is a contract.** `test_eval_record.py` pins it. Adding a field is fine;
    silently renaming or dropping one breaks every recorded row that came before.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

# How a run ended. `refused` never reaches the graph — the quota gate answers first — but
# it belongs in the same table, because "how often are people turned away" is a question
# about runs.
Outcome = str  # "completed" | "failed" | "stopped" | "refused"


@dataclass
class RunRecord:
    """Everything worth knowing about one generation, in one flat row."""

    # --- what was asked -------------------------------------------------------------
    outcome: Outcome
    input_kind: str  # "text" | "sql" | "openapi"
    intent: str  # "create" | "edit" | "replace" | "answer"

    # --- what came out --------------------------------------------------------------
    # None where the stage never ran: a question answers without planning anything, and a
    # failed run may not have reached the planner at all.
    nodes: int | None = None
    edges: int | None = None
    groups: int | None = None
    shapes: int | None = None
    components_specified: int | None = None
    assumptions: int | None = None

    # --- how well it went -----------------------------------------------------------
    # The headline pair. `degraded` must never rise: a degraded run looks identical to a
    # good one until you read the picture. `repairs` is a direct read on raw model
    # quality — the shorter it gets, the better the prompt.
    degraded: bool = False
    degraded_reason: str = ""
    repairs: int = 0
    # True when the per-run cost cap fired and a discretionary call (the plan repair pass,
    # the vision Critic) was skipped. Report-only — a capped run still produced a diagram —
    # but it should never be mistaken for a first-pass-clean one.
    budget_capped: bool = False
    # Issue kinds raised anywhere in the run, and how many of each. Kinds come from the
    # validator (`missing_components`, `isolated_node`, …) and the critic (`overlap`,
    # `dangling_arrow`, `vision:crowding`, …).
    issues: dict[str, int] = field(default_factory=dict)
    blocking_issues: int = 0
    # Layout passes beyond the first. 0 means the composition was clean first time.
    refines: int = 0
    first_pass_clean: bool | None = None

    # --- edits ----------------------------------------------------------------------
    ops_proposed: int | None = None
    ops_applied: int | None = None
    ops_rejected: int | None = None

    # --- what it cost ---------------------------------------------------------------
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    # False when a model that did work has no price on file — the money figure is then a
    # lower bound, and saying so is better than a confident wrong number.
    cost_known: bool = True
    stage_ms: dict[str, float] = field(default_factory=dict)
    total_ms: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def issue_count(self) -> int:
        return sum(self.issues.values())


def _issue_kinds(items: list[Any]) -> Counter:
    """Count `kind` across a list of issues, whether they are dicts or objects."""
    counter: Counter = Counter()
    for item in items or []:
        kind = item.get("kind") if isinstance(item, dict) else getattr(item, "kind", None)
        if kind:
            counter[str(kind)] += 1
    return counter


def _severity(item: Any) -> str:
    return str(
        (item.get("severity") if isinstance(item, dict) else getattr(item, "severity", "")) or ""
    )


def record_from_run(
    state: dict[str, Any],
    *,
    outcome: Outcome,
    passes: list[dict[str, Any]] | None = None,
    stage_ms: dict[str, float] | None = None,
    total_ms: float = 0.0,
    meter: Any = None,
    shapes: int | None = None,
) -> RunRecord:
    """Build the row from the graph's final state plus what only the caller knows.

    `state` is the merged state the engine leaves behind. `passes` is the critic's
    per-pass output, which the SSE endpoint collects as it streams and the state does not
    retain. `shapes` is what actually reached the canvas, which can differ from the plan's
    node count when a run is stopped part-way.
    """
    report = state.get("plan_report") or {}
    spec = state.get("spec")
    passes = passes or []

    issues: Counter = Counter()
    issues += _issue_kinds(report.get("issues", []))
    blocking = sum(1 for i in report.get("issues", []) if _severity(i) == "error")
    for critique in passes:
        issues += _issue_kinds(critique.get("issues", []))

    intent = str(report.get("intent") or ("answer" if state.get("answered") else "create"))

    # The first critic pass is the one that says whether the composition was right without
    # help. Later passes only report on a layout that has already been widened.
    first_pass_clean: bool | None = None
    if passes:
        first_pass_clean = not passes[0].get("has_issues", False)

    if meter is not None:
        meter.collect()

    return RunRecord(
        outcome=outcome,
        input_kind=str(state.get("input_kind") or "text"),
        intent=intent,
        nodes=report.get("nodes"),
        edges=report.get("edges"),
        groups=report.get("groups"),
        shapes=shapes,
        components_specified=len(spec.component_names) if spec is not None else None,
        assumptions=len(spec.assumptions) if spec is not None else None,
        degraded=bool(report.get("degraded")),
        degraded_reason=str(report.get("degraded") or ""),
        repairs=len(report.get("fixes", []) or []),
        budget_capped=bool(state.get("budget_capped")),
        issues=dict(issues),
        blocking_issues=blocking,
        # `iterations` counts drawer visits; the first one is not a refine.
        refines=max(0, int(state.get("iterations", 0) or 0) - 1),
        first_pass_clean=first_pass_clean,
        ops_proposed=(
            len(report.get("applied", []) or []) + len(report.get("rejected", []) or [])
            if intent in ("edit", "replace")
            else None
        ),
        ops_applied=len(report.get("applied", []) or []) if intent in ("edit", "replace") else None,
        ops_rejected=(
            len(report.get("rejected", []) or []) if intent in ("edit", "replace") else None
        ),
        input_tokens=meter.input_tokens if meter is not None else 0,
        output_tokens=meter.output_tokens if meter is not None else 0,
        cost_usd=meter.cost_usd if meter is not None else 0.0,
        cost_known=meter.cost_known if meter is not None else True,
        stage_ms={k: round(v, 1) for k, v in (stage_ms or {}).items()},
        total_ms=round(total_ms, 1),
    )
