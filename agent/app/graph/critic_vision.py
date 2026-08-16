"""Vision half of the Critic — an LLM actually *looks at* the rendered diagram.

Renders the current actions to a PNG (`render.py`), sends the image to a multimodal
model via structured output, and returns a typed `VisionCritique`. Best-effort: returns
`None` with no LLM key or on any failure, so the deterministic geometry critic still
drives the refine loop. This is the genuine "self-correct with vision" signal.
"""

from __future__ import annotations

import base64

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.graph.render import render_actions
from app.llm import build_chat_model, resolve_config
from app.schema import AgentAction


class VisionIssue(BaseModel):
    kind: str = Field(description="overlap | crowding | readability | arrows | balance | other")
    message: str = Field(description="one short sentence describing the visual problem")


class VisionCritique(BaseModel):
    has_issues: bool = Field(description="true if the layout has any visual problem")
    issues: list[VisionIssue] = Field(default_factory=list)
    summary: str = Field(default="", description="one-line overall assessment of the layout")


_SYSTEM = (
    "You are a diagram layout critic. You are shown a rendered node/edge diagram. "
    "Judge ONLY its visual layout quality: overlapping or crowded boxes, text that "
    "overflows its box, tangled or overlapping arrows, and overall balance/whitespace. "
    "Do NOT critique the underlying idea, wording, or completeness. Be strict but "
    "concise. If the layout is clean, set has_issues=false and return an empty issues list."
)


async def critique_image(actions: list[AgentAction], *, context: str = "") -> VisionCritique | None:
    """Render the diagram and ask a vision model to critique its layout. None on no-key/failure."""
    cfg = resolve_config()
    if not cfg.api_key:
        return None

    try:
        png = render_actions(actions)
    except Exception:
        return None
    if not png:
        return None

    b64 = base64.b64encode(png).decode()
    human = HumanMessage(
        content=[
            {
                "type": "text",
                "text": f"Critique this diagram's visual layout. Context: {context[:200] or 'n/a'}",
            },
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]
    )

    try:
        model = build_chat_model(cfg).with_structured_output(
            VisionCritique, method="function_calling"
        )
        result = await model.ainvoke([SystemMessage(content=_SYSTEM), human])
    except Exception:
        return None

    return result if isinstance(result, VisionCritique) else None
