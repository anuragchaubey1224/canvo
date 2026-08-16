"""LLM planner — turn a freeform description into a structured diagram graph.

Uses Claude/OpenAI tool-calling (structured output) so the model returns a typed
`DiagramPlan` (nodes + directed edges); the deterministic Drawer then lays it out.
Returns None when no LLM key is configured or the call fails, so the graph falls
back to its stub and the no-key deterministic paths keep working.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.llm import build_chat_model, resolve_config


class PlanNode(BaseModel):
    id: str = Field(description="short unique id, e.g. 'login'")
    label: str = Field(description="short human-readable label")


class PlanEdge(BaseModel):
    source: str = Field(description="id of the source node")
    target: str = Field(description="id of the target node")
    label: str | None = Field(default=None, description="optional edge label")


class DiagramPlan(BaseModel):
    nodes: list[PlanNode] = Field(default_factory=list)
    edges: list[PlanEdge] = Field(default_factory=list)


_SYSTEM = (
    "You turn a description into a small directed diagram graph. "
    "Return concise nodes (at most 12, short labels) and directed edges that "
    "reference node ids. Prefer a clear flow. Do not invent unrelated nodes."
)


async def plan_from_text(message: str) -> DiagramPlan | None:
    cfg = resolve_config()
    if not cfg.api_key or not message.strip():
        return None

    model = build_chat_model(cfg).with_structured_output(DiagramPlan, method="function_calling")
    try:
        plan = await model.ainvoke([("system", _SYSTEM), ("human", message)])
    except Exception:
        return None

    return plan if isinstance(plan, DiagramPlan) and plan.nodes else None
