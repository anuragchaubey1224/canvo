"""Provider abstraction — supports "bring your own key" (BYOK).

Canvo can call Claude directly, route through **OpenRouter** (an
OpenAI-compatible gateway to many models), or hit **any OpenAI-compatible**
endpoint. The provider + key can come from server env OR be supplied
per-request by the user (BYOK) — so users can spend on their own quota.

Security: user-supplied keys are used for that request only and are NEVER
logged or persisted (see PLAN.md §6c). Always serve over HTTPS in prod.

Phase 0: `build_chat_model` isn't called yet (nodes are hardcoded stubs).
Wire it into planner/drawer/critic when replacing the stubs (PLAN.md §5).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMConfig:
    provider: str = "anthropic"  # "anthropic" | "openrouter" | "openai-compatible"
    model: str = "claude-sonnet-5"
    api_key: str | None = None
    base_url: str | None = None  # for openrouter / custom gateways
    # Latency budget. Retries are deliberately low: every stage degrades gracefully (the
    # planner falls back to the direct path, the vision critic to geometry alone), so a
    # slow provider should cost one wasted wait, not three stacked ones.
    timeout: int = 60
    max_retries: int = 1
    max_tokens: int = 4096


# Per-stage ceilings.
#
# `max_tokens` is NOT a length hint — on a thinking model (Gemini 3.x, o-series, DeepSeek
# R1) the reasoning tokens are billed against this same budget before a single visible
# token appears. Caps sized to the *visible* answer therefore truncate mid-output: a
# 1400-token cap cut the spec off after FLOW (losing PHASES and ASSUMPTIONS), and a
# 3000-token cap cut the planner's tool call in half, which surfaces as a parse error and
# a fallback diagram. Keep these generous; they exist to stop a runaway, not to save
# money, and latency is governed by `timeout`.
_ROLE_LIMITS: dict[str, dict[str, int]] = {
    "spec": {"timeout": 60, "max_tokens": 4000},
    "plan": {"timeout": 90, "max_tokens": 8000},
    "vision": {"timeout": 45, "max_tokens": 2000, "max_retries": 0},
}


def resolve_config(user_override: dict | None = None, *, role: str | None = None) -> LLMConfig:
    """Merge server defaults (env) with an optional per-request BYOK override.

    User-supplied values win, so a request can fully redirect to the user's
    own provider + key without touching server config.

    `role` names the pipeline stage ("spec", "plan", "vision"). A stage can be pointed at
    a cheaper model via `LLM_<ROLE>_MODEL` — the Spec Writer does extraction, not spatial
    reasoning, so it runs fine on a small model while the planner stays on the good one.
    A BYOK model always wins: the user asked for that model explicitly.
    """
    cfg = LLMConfig(
        provider=os.getenv("LLM_PROVIDER", "anthropic"),
        model=os.getenv("LLM_MODEL", "claude-sonnet-5"),
        api_key=os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL") or None,
    )
    if role:
        cfg.model = os.getenv(f"LLM_{role.upper()}_MODEL") or cfg.model
        for field, value in _ROLE_LIMITS.get(role, {}).items():
            setattr(cfg, field, value)
    if user_override:
        cfg.provider = user_override.get("provider") or cfg.provider
        cfg.model = user_override.get("model") or cfg.model
        cfg.api_key = user_override.get("api_key") or cfg.api_key
        cfg.base_url = user_override.get("base_url") or cfg.base_url
    return cfg


# How to ask for a typed answer, in order of preference. Providers differ in which they
# honour behind an OpenAI-compatible gateway, and a refusal is indistinguishable from a bad
# answer at the call site — so try the next one rather than give up.
_METHODS = ("function_calling", "json_schema")


def meter_config(meter) -> dict:
    """The `config=` to pass to `ainvoke` so this call is counted.

    `meter` is an `app.usage.UsageMeter` or None — typed loosely to keep this module free
    of an import cycle, and because "no meter" is a normal state: a unit test calling a
    stubbed model has nothing to account for.
    """
    return {"callbacks": meter.callbacks} if meter is not None else {}


async def structured_call(cfg: LLMConfig, system: str, human: str, schema, stage: str, meter=None):
    """One typed request, retried across structured-output methods. None if all fail."""
    import logging

    logger = logging.getLogger(__name__)
    for method in _METHODS:
        try:
            model = build_chat_model(cfg).with_structured_output(schema, method=method)
            result = await model.ainvoke(
                [("system", system), ("human", human)], config=meter_config(meter)
            )
        except Exception:
            logger.warning("%s failed via %s (model=%s)", stage, method, cfg.model, exc_info=True)
            continue
        if isinstance(result, schema):
            return result
        logger.warning("%s returned an unusable shape via %s", stage, method)
    return None


def build_chat_model(cfg: LLMConfig):
    """Return a LangChain chat model for the resolved provider.

    Anthropic uses the native integration; OpenRouter and any other
    OpenAI-compatible gateway share the ChatOpenAI path (just a base_url swap).
    """
    # Cap output explicitly: our calls return small structured plans/critiques, and an
    # uncapped request can exceed a metered key's affordability check (OpenRouter 402s
    # when the model's default max_tokens outruns the key's remaining credit).
    if cfg.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        kwargs: dict[str, Any] = {
            "model": cfg.model,
            "api_key": cfg.api_key,
            "max_tokens": cfg.max_tokens,
            "timeout": cfg.timeout,
            "max_retries": cfg.max_retries,
        }
        return ChatAnthropic(**kwargs)

    # OpenRouter / openai-compatible. Requires `langchain-openai` (see requirements.txt).
    from langchain_openai import ChatOpenAI

    kwargs = {
        "model": cfg.model,
        "api_key": cfg.api_key,
        "base_url": cfg.base_url or "https://openrouter.ai/api/v1",
        "max_tokens": cfg.max_tokens,
        "timeout": cfg.timeout,
        "max_retries": cfg.max_retries,
    }
    return ChatOpenAI(**kwargs)
