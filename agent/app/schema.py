"""Typed contract between the tldraw client and the agent service.

Mirrors `shared/actions.schema.json`. The client sends an `AgentInput`
(the user's message + a snapshot of what's on the canvas) and receives a
stream of `AgentAction`s that it applies to the tldraw canvas.

Keep this in sync with the client-side Zod schema — a contract test guards
against drift (see PLAN.md §4).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# The only colour names the client can render (tldraw's palette). Part of the contract,
# mirrored by COLOR_TOKENS in web/src/lib/applyActions.ts. The client silently greys out
# anything else, so the server validates here instead of trusting a planner's invention —
# one model returning "#3B82F6" or "blue-500" is enough to drain a whole diagram of colour.
COLOR_TOKENS = frozenset(
    {
        "black",
        "grey",
        "light-violet",
        "violet",
        "blue",
        "light-blue",
        "yellow",
        "orange",
        "green",
        "light-green",
        "light-red",
        "red",
        "white",
    }
)


def color_token(value: str | None) -> str | None:
    """Normalise a planner-supplied colour to a renderable token, or None if it isn't one."""
    if not value:
        return None
    token = value.strip().lower().replace("_", "-").replace(" ", "-")
    return token if token in COLOR_TOKENS else None


class Shape(BaseModel):
    """A minimal shape the client knows how to render/apply."""

    id: str
    type: str  # "geo" | "arrow" | "container" | "frame" | "text" | ...
    x: float
    y: float
    w: float = 0
    h: float = 0
    text: str | None = None
    # For arrows/connectors: bind endpoints to other shapes (e.g. ERD relations).
    from_id: str | None = None
    to_id: str | None = None
    # Semantic styling (ADR-013: open set — the client's ShapeRegistry maps known kinds
    # to renderers and falls back to a plain box for anything it doesn't recognize).
    kind: str | None = None  # "service" | "datastore" | "decision" | "client" | ...
    subtitle: str | None = None
    color: str | None = None  # tldraw color token, e.g. "blue" | "violet" | "orange"
    parent_id: str | None = None  # membership: id of the container this shape sits in
    icon: str | None = None  # icon name, e.g. "server" | "database" | "shield" (open set)
    # Routed arrows (our own obstacle-avoiding router): absolute orthogonal waypoints as
    # a flat [x0,y0,x1,y1,...] list, plus an anchor for the label chip. Arrows without
    # points fall back to the client's bound elbow arrows.
    points: list[float] | None = None
    label_x: float | None = None
    label_y: float | None = None


class CanvasContext(BaseModel):
    """What the agent 'sees' each turn (visual grounding)."""

    focused_shapes: list[Shape] = Field(default_factory=list)
    blurry_shapes: list[Shape] = Field(default_factory=list)
    screenshot: str | None = None  # base64 PNG; used by the Critic (vision)


class LLMOverride(BaseModel):
    """Optional per-request "bring your own key" (BYOK) override.

    Lets a user route the run through their own provider/key (e.g. OpenRouter
    or any OpenAI-compatible gateway). Never logged or persisted. See app/llm.py.
    """

    provider: str | None = None  # "anthropic" | "openrouter" | "openai-compatible"
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None


class AgentInput(BaseModel):
    """Client → service."""

    message: str = ""  # optional: pure spec/payload runs need no instruction
    canvas_context: CanvasContext = Field(default_factory=CanvasContext)
    session_id: str = "dev"
    llm: LLMOverride | None = None  # BYOK; falls back to server env when absent
    # Input routing. `payload` carries raw material (SQL DDL, an OpenAPI doc, code…);
    # `input_kind` optionally forces the route, else the Router auto-detects from message/payload.
    input_kind: str | None = None  # "text" | "sql" | "openapi" | "code"
    payload: str | None = None
    # Critic: run the vision self-correction pass. None → server default (on when a key exists).
    enable_vision: bool | None = None
    # Spec Writer: expand a vague request into an explicit spec before planning.
    # None → server default (on). Off = one LLM call instead of two, thinner diagrams.
    enable_spec: bool | None = None


class AgentAction(BaseModel):
    """Service → client (streamed). One canvas operation."""

    type: Literal["create", "update", "delete"]
    shape: Shape | None = None  # for create / update
    shape_id: str | None = None  # for delete, or to reference an update target
