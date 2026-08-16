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


def resolve_config(user_override: dict | None = None) -> LLMConfig:
    """Merge server defaults (env) with an optional per-request BYOK override.

    User-supplied values win, so a request can fully redirect to the user's
    own provider + key without touching server config.
    """
    cfg = LLMConfig(
        provider=os.getenv("LLM_PROVIDER", "anthropic"),
        model=os.getenv("LLM_MODEL", "claude-sonnet-5"),
        api_key=os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL") or None,
    )
    if user_override:
        cfg.provider = user_override.get("provider") or cfg.provider
        cfg.model = user_override.get("model") or cfg.model
        cfg.api_key = user_override.get("api_key") or cfg.api_key
        cfg.base_url = user_override.get("base_url") or cfg.base_url
    return cfg


def build_chat_model(cfg: LLMConfig):
    """Return a LangChain chat model for the resolved provider.

    Anthropic uses the native integration; OpenRouter and any other
    OpenAI-compatible gateway share the ChatOpenAI path (just a base_url swap).
    """
    if cfg.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        kwargs: dict[str, Any] = {"model": cfg.model, "api_key": cfg.api_key}
        return ChatAnthropic(**kwargs)

    # OpenRouter / openai-compatible. Requires `langchain-openai` (see requirements.txt).
    from langchain_openai import ChatOpenAI

    kwargs = {
        "model": cfg.model,
        "api_key": cfg.api_key,
        "base_url": cfg.base_url or "https://openrouter.ai/api/v1",
    }
    return ChatOpenAI(**kwargs)
