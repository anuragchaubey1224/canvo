"""Safety layer (Phase-0 stubs).

Full implementations land in v1 (see PLAN.md §6c):
  - cost cap per run          (hard-stop when cost_usd exceeds MAX_COST_USD)
  - iteration cap             (enforced in the graph's conditional edge)
  - prompt-injection defense  (keep user text separate from system instructions)
  - schema validate + sanitize (drop invalid shape ids / clamp out-of-bounds coords)
"""

from __future__ import annotations

MAX_COST_USD = 0.50
MAX_ITERATIONS = 3


def within_budget(cost_usd: float) -> bool:
    return cost_usd < MAX_COST_USD
