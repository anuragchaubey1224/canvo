"""Typed contract between the tldraw client and the agent service.

Mirrors `shared/actions.schema.json`. The client sends an `AgentInput`
(the user's message + a snapshot of what's on the canvas) and receives a
stream of `AgentAction`s that it applies to the tldraw canvas.

Keep this in sync with the client-side Zod schema — a contract test guards
against drift (see PLAN.md §4).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Shape(BaseModel):
    """A minimal shape the client knows how to render/apply."""

    id: str
    type: str  # "geo" | "arrow" | "text" | ...
    x: float
    y: float
    w: float = 0
    h: float = 0
    text: Optional[str] = None
    # For arrows/connectors: bind endpoints to other shapes (e.g. ERD relations).
    from_id: Optional[str] = None
    to_id: Optional[str] = None


class CanvasContext(BaseModel):
    """What the agent 'sees' each turn (visual grounding)."""

    focused_shapes: list[Shape] = Field(default_factory=list)
    blurry_shapes: list[Shape] = Field(default_factory=list)
    screenshot: Optional[str] = None  # base64 PNG; used by the Critic (vision)


class LLMOverride(BaseModel):
    """Optional per-request "bring your own key" (BYOK) override.

    Lets a user route the run through their own provider/key (e.g. OpenRouter
    or any OpenAI-compatible gateway). Never logged or persisted. See app/llm.py.
    """

    provider: Optional[str] = None  # "anthropic" | "openrouter" | "openai-compatible"
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class AgentInput(BaseModel):
    """Client → service."""

    message: str
    canvas_context: CanvasContext = Field(default_factory=CanvasContext)
    session_id: str = "dev"
    llm: Optional[LLMOverride] = None  # BYOK; falls back to server env when absent
    # Input routing. `payload` carries raw material (SQL DDL, an OpenAPI doc, code…);
    # `input_kind` optionally forces the route, else the Router auto-detects from message/payload.
    input_kind: Optional[str] = None  # "text" | "sql" | "openapi" | "code"
    payload: Optional[str] = None


class AgentAction(BaseModel):
    """Service → client (streamed). One canvas operation."""

    type: Literal["create", "update", "delete"]
    shape: Optional[Shape] = None  # for create / update
    shape_id: Optional[str] = None  # for delete, or to reference an update target
