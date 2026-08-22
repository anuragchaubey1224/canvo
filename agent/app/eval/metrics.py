"""Many `RunRecord`s → aggregate numbers. See EVAL-PLAN.md §4 (Metrics worth a number, Gates).

Where `record.py` answers "what happened in this one run", this module answers "how is
the suite doing overall" — and, for Tier 1, whether that overall picture clears the two
gates that are never negotiable: a degraded run, or a validator issue nothing repaired.

`records` is keyed by case/run id throughout, on purpose: "94% clean" is not actionable,
"case sql-wide-schema-needs-refine is dirty" is (EVAL-PLAN.md §8, "aggregates hide
regressions").
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.eval.record import RunRecord


def _rate(hits: int, total: int) -> float | None:
    return round(hits / total, 4) if total else None


def _pct(x: float | None) -> str:
    return f"{x * 100:.1f}%" if x is not None else "n/a"


@dataclass
class AggregateReport:
    n: int
    structural_validity: float | None  # fraction with zero blocking validator issues
    first_pass_clean_rate: float | None  # among runs a critic pass actually judged
    refine_rate: float | None  # fraction that needed >=1 refine
    degradation_rate: float | None
    mean_repairs: float | None
    degraded_cases: list[str] = field(default_factory=list)
    invalid_cases: list[str] = field(default_factory=list)  # blocking_issues > 0

    @property
    def passes_hard_gates(self) -> bool:
        """EVAL-PLAN.md §4: any degraded run, or structural validity below 100%, blocks."""
        return not self.degraded_cases and not self.invalid_cases

    def render(self) -> str:
        lines = [
            f"Tier 1 — {self.n} case(s)",
            f"  structural validity   {_pct(self.structural_validity)}",
            f"  first-pass clean      {_pct(self.first_pass_clean_rate)}",
            f"  refine rate           {_pct(self.refine_rate)}",
            f"  degradation rate      {_pct(self.degradation_rate)}",
            "  mean repairs          "
            + (f"{self.mean_repairs}" if self.mean_repairs is not None else "n/a"),
        ]
        if self.invalid_cases:
            lines.append(f"  INVALID  (blocking validator issues): {', '.join(self.invalid_cases)}")
        if self.degraded_cases:
            lines.append(
                f"  DEGRADED (stage failed, fallback drew it): {', '.join(self.degraded_cases)}"
            )
        return "\n".join(lines)


def aggregate(records: Mapping[str, RunRecord]) -> AggregateReport:
    """`records` keyed by case id, so a failure in the report can be named, not just counted."""
    n = len(records)
    invalid = sorted(cid for cid, r in records.items() if r.blocking_issues > 0)
    degraded = sorted(cid for cid, r in records.items() if r.degraded)

    first_pass_known = [
        r.first_pass_clean for r in records.values() if r.first_pass_clean is not None
    ]
    repairs = [r.repairs for r in records.values()]

    return AggregateReport(
        n=n,
        structural_validity=_rate(n - len(invalid), n),
        first_pass_clean_rate=_rate(sum(first_pass_known), len(first_pass_known)),
        refine_rate=_rate(sum(1 for r in records.values() if r.refines >= 1), n),
        degradation_rate=_rate(len(degraded), n),
        mean_repairs=round(sum(repairs) / n, 2) if n else None,
        degraded_cases=degraded,
        invalid_cases=invalid,
    )
