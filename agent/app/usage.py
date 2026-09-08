"""What a run cost.

Every model call in the pipeline goes through a chat model built by `app.llm`, and every
one of them is billed. A `UsageMeter` is created per run, passed to every model call as a
LangChain callback, and ends up holding the token counts for the whole graph broken down
by model. Cost is derived from those counts where we know the price.

The meter is read two ways: `snapshot_cost()` mid-run, so `guardrails.within_budget()` can
skip a discretionary call that would blow the per-run cap; and the full totals at the end,
folded into the run's `RunRecord`.

Two deliberate limits:

  - **Tokens are always recorded; cost sometimes is not.** Prices change and are not
    discoverable at runtime, so `PRICES` is a hand-maintained table. A model that is not
    in it still gets its tokens counted, and `cost_known` says the money figure is
    incomplete. Reporting a confident $0.00 for an unpriced model would be worse than
    admitting we don't know.
  - **It observes, it does not decide.** Nothing here refuses a call. Enforcement belongs
    to the caller, which can read `total_usd` and stop.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.callbacks import UsageMetadataCallbackHandler

# USD per 1M tokens, (input, output). Checked against provider pricing pages on
# 2026-08-22; re-check when changing models. A model missing from this table is not an
# error — see `cost_known`.
PRICES: dict[str, tuple[float, float]] = {
    # OpenRouter model ids, which is what this deployment uses.
    "google/gemini-3.7-flash": (0.30, 2.50),
    "google/gemini-3.7-pro": (1.25, 10.00),
    "anthropic/claude-sonnet-5": (3.00, 15.00),
    "anthropic/claude-haiku-4.5": (1.00, 5.00),
    # Anthropic direct ids, for the non-gateway path.
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
}


def price_of(model: str) -> tuple[float, float] | None:
    """Input/output price per 1M tokens, or None when we have no figure for this model."""
    if model in PRICES:
        return PRICES[model]
    # Gateways prefix the vendor ("openrouter/google/gemini-…"); match on the tail so a
    # routing change doesn't silently drop pricing.
    tail = model.rsplit("/", 2)
    for i in range(1, len(tail) + 1):
        candidate = "/".join(tail[-i:])
        if candidate in PRICES:
            return PRICES[candidate]
    return None


@dataclass
class ModelUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class UsageMeter:
    """Token and cost accounting for one run.

    Pass `meter.callbacks` to every `ainvoke`; read the totals when the run ends.
    """

    by_model: dict[str, ModelUsage] = field(default_factory=dict)
    _handler: UsageMetadataCallbackHandler = field(
        default_factory=UsageMetadataCallbackHandler, repr=False
    )

    @property
    def callbacks(self) -> list:
        """What to hand LangChain: `config={"callbacks": meter.callbacks}`."""
        return [self._handler]

    def collect(self) -> None:
        """Fold whatever the handler has seen into `by_model`.

        Called before reading totals rather than continuously, because the handler
        accumulates its own dict and we want one place where the two representations meet.
        Idempotent — each entry is overwritten from the handler's running total, so it is
        safe to call repeatedly during a run.
        """
        for model, usage in (self._handler.usage_metadata or {}).items():
            entry = self.by_model.setdefault(model, ModelUsage())
            # LangChain normalises these across providers; a provider that reports
            # neither leaves them absent rather than zero.
            entry.input_tokens = int(usage.get("input_tokens", 0) or 0)
            entry.output_tokens = int(usage.get("output_tokens", 0) or 0)

    def snapshot_cost(self) -> float:
        """Cost of everything billed so far this run. `collect()` then read, for the
        mid-run budget checks in `guardrails.within_budget()` — the live `cost_usd`
        property reads `by_model`, which only `collect()` refreshes."""
        self.collect()
        return self.cost_usd

    @property
    def input_tokens(self) -> int:
        return sum(u.input_tokens for u in self.by_model.values())

    @property
    def output_tokens(self) -> int:
        return sum(u.output_tokens for u in self.by_model.values())

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self) -> float:
        """What we can account for. Unpriced models contribute nothing — check
        `cost_known` before treating this as the whole bill."""
        total = 0.0
        for model, usage in self.by_model.items():
            price = price_of(model)
            if price is None:
                continue
            per_in, per_out = price
            total += (usage.input_tokens * per_in + usage.output_tokens * per_out) / 1_000_000
        return round(total, 6)

    @property
    def cost_known(self) -> bool:
        """False when at least one model that did work has no price on file."""
        return all(
            price_of(model) is not None
            for model, usage in self.by_model.items()
            if usage.total_tokens
        )

    @property
    def unpriced_models(self) -> list[str]:
        return sorted(
            model
            for model, usage in self.by_model.items()
            if usage.total_tokens and price_of(model) is None
        )
