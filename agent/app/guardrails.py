"""Safety layer.

  - **iteration cap** — enforced in the graph's conditional edge (`build._should_refine`).
  - **per-run cost cap** — `within_budget()` is consulted before every *discretionary*
    model call left in a run (the planner's one repair pass, the vision Critic). It never
    aborts a run outright: the core plan is already drawn by then, so crossing the cap
    trims the extras and lets what exists stand. The run is marked `budget_capped` so a
    capped run is never mistaken for a clean one.

Still stubs, for v1 (see PLAN.md §6d):
  - prompt-injection defense  (keep user text separate from system instructions)
  - schema validate + sanitize (drop invalid shape ids / clamp out-of-bounds coords)
"""

from __future__ import annotations

import os

# What one generation may spend on model tokens before its discretionary calls are
# skipped. Read at call time, like the quota limits, so a deployment can retune it with an
# env change and a restart. `0` disables the cap — the escape hatch for a live demo.
DEFAULT_MAX_RUN_COST_USD = 0.50
MAX_ITERATIONS = 3


def max_run_cost_usd() -> float:
    """The per-run ceiling, from the environment. A typo falls back to the default rather
    than silently meaning "unlimited"; a negative value is clamped to `0` (disabled)."""
    raw = os.getenv("MAX_RUN_COST_USD", "").strip()
    if not raw:
        return DEFAULT_MAX_RUN_COST_USD
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_MAX_RUN_COST_USD


def within_budget(cost_usd: float) -> bool:
    """Whether a run that has spent `cost_usd` so far may make another discretionary call.

    Always true when the cap is `0` (disabled) or when cost is unknown and reported as
    `0.0` — we only cap what we can price (see `UsageMeter.cost_known`).
    """
    cap = max_run_cost_usd()
    return cap == 0.0 or cost_usd < cap
