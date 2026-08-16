"""LLM planner — turn a freeform description into a structured diagram graph.

Uses Claude/OpenAI tool-calling (structured output) so the model returns a typed
`DiagramPlan` (nodes + directed edges + optional groups); the deterministic Drawer
then lays it out. Returns None when no LLM key is configured or the call fails, so
the graph falls back to its stub and the no-key deterministic paths keep working.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.llm import build_chat_model, resolve_config


class PlanNode(BaseModel):
    id: str = Field(description="short unique id, e.g. 'login'")
    label: str = Field(description="short human-readable label")
    kind: str | None = Field(
        default=None,
        description=(
            "semantic kind: service | datastore | decision | client | external | queue "
            "| start | end | note. Use 'decision' for yes/no branch points, 'datastore' "
            "for databases/caches, 'client' for apps/browsers, 'external' for third parties."
        ),
    )
    subtitle: str | None = Field(
        default=None,
        description="optional short detail line, e.g. 'POST /auth/login' or 'HS256/RS256'",
    )
    group: str | None = Field(
        default=None, description="id of the group/stage this node belongs to (see groups)"
    )
    icon: str | None = Field(
        default=None,
        description=(
            "optional icon: monitor | server | shield | database | cloud | queue | key "
            "| gateway | api | lock | refresh | user | note | play | flag"
        ),
    )


class PlanEdge(BaseModel):
    source: str = Field(description="id of the source node")
    target: str = Field(description="id of the target node")
    label: str | None = Field(
        default=None,
        description=(
            "optional edge label: AT MOST 2 short words (e.g. 'credentials', 'valid', "
            "'yes'). Omit for obvious transitions."
        ),
    )


class PlanGroup(BaseModel):
    id: str = Field(description="short unique group id, e.g. 'issuance'")
    label: str = Field(description="group title, e.g. '1. Login & Token Issuance'")
    color: str | None = Field(
        default=None,
        description="optional tldraw color token: blue|violet|orange|green|light-blue|yellow",
    )


class DiagramPlan(BaseModel):
    title: str | None = Field(
        default=None, description="short diagram title, e.g. 'JWT Authentication Workflow'"
    )
    nodes: list[PlanNode] = Field(default_factory=list)
    edges: list[PlanEdge] = Field(default_factory=list)
    groups: list[PlanGroup] = Field(
        default_factory=list,
        description="optional stages/swimlanes; use them when the flow has distinct phases",
    )


_SYSTEM = (
    "You turn a description into a small directed diagram graph.\n"
    "Return concise nodes (at most 16, short labels) and directed edges that reference "
    "node ids. Prefer a clear flow. Do not invent unrelated nodes.\n"
    "Give each node a semantic `kind` (service, datastore, decision, client, external, "
    "queue, start, end, note) and, where useful, a short `subtitle` with the concrete "
    "detail (an endpoint, a protocol, a table).\n"
    "When the flow has distinct phases or lanes (e.g. '1. Login & Token Issuance', "
    "'2. Token Anatomy'), define numbered `groups` and assign each node's `group`. "
    "Use 2-5 groups for multi-phase flows, with 2-6 nodes per group; skip groups for "
    "simple linear ones. When you use groups, assign EVERY node to one (a start/end "
    "belongs in the phase where the flow begins/ends — avoid ungrouped nodes).\n"
    "Keep edge labels to AT MOST 2 short words; omit labels on obvious transitions. "
    "Minimize edges that jump between non-adjacent groups."
)


async def plan_from_text(message: str, llm_override: dict | None = None) -> DiagramPlan | None:
    cfg = resolve_config(llm_override)
    if not cfg.api_key or not message.strip():
        return None

    model = build_chat_model(cfg).with_structured_output(DiagramPlan, method="function_calling")
    try:
        plan = await model.ainvoke([("system", _SYSTEM), ("human", message)])
    except Exception:
        return None

    if not (isinstance(plan, DiagramPlan) and plan.nodes):
        return None

    # Sanitize: group references must point at declared groups (an LLM slip here would
    # otherwise strand nodes outside every container).
    group_ids = {g.id for g in plan.groups}
    for node in plan.nodes:
        if node.group and node.group not in group_ids:
            node.group = None
    return plan
