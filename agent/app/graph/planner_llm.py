"""LLM planner — turn a diagram spec (or raw text) into a structured diagram graph.

Uses Claude/OpenAI tool-calling (structured output) so the model returns a typed
`DiagramPlan` (nodes + directed edges + optional groups); the deterministic Drawer
then lays it out. Returns None when no LLM key is configured or the call fails, so
the graph falls back to its stub and the no-key deterministic paths keep working.

Two prompts, because the job is genuinely different in each case:
  - `_SYSTEM_SPEC`   the Spec Writer already did the thinking; the planner's only job is
                     complete, faithful *mapping*. This is the normal path.
  - `_SYSTEM_DIRECT` no spec (no key for stage one, a parse miss, or a very short input)
                     — the planner has to understand and structure in one pass.

`refine_plan` is the repair pass: the validator hands over exactly what's wrong and the
planner returns a corrected plan. Called at most once per run (see nodes.planner).
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.llm import LLMConfig, build_chat_model, meter_config, resolve_config

logger = logging.getLogger(__name__)

# How to ask for a typed answer, in order of preference. Providers differ in which they
# actually honour behind an OpenAI-compatible gateway, and a refusal is indistinguishable
# from a bad plan at the call site — so try the next one rather than fall back to a stub.
_METHODS = ("function_calling", "json_schema")


class PlanNode(BaseModel):
    id: str = Field(description="short unique id, e.g. 'login'")
    label: str = Field(description="1-3 words, no detail — details belong in `subtitle`")
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
        description=(
            "the concrete detail for this node, under ~28 chars: an endpoint, method, "
            "status code, protocol or algorithm — e.g. 'POST /auth/login', 'HS256', '401'"
        ),
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
        description=(
            "one of these exact strings, nothing else — not a hex code, not a shade: "
            "blue, violet, orange, green, light-blue, yellow, red. Omit if unsure."
        ),
    )


class DiagramPlan(BaseModel):
    title: str | None = Field(
        default=None, description="short diagram title, e.g. 'JWT Authentication Workflow'"
    )
    nodes: list[PlanNode] = Field(
        default_factory=list,
        description="10-20 nodes for a normal request; 24 is the hard ceiling",
    )
    edges: list[PlanEdge] = Field(
        default_factory=list,
        description="one per flow step, including error and alternate paths",
    )
    groups: list[PlanGroup] = Field(
        default_factory=list,
        description="3-5 numbered phases/swimlanes; every node should belong to one",
    )


_SYSTEM_SPEC = """You convert a diagram SPEC into a node/edge graph. The spec is the source \
of truth: map it completely and faithfully. Do not summarize it, do not add to it.

Mapping:
- Every COMPONENT becomes exactly one node, keeping the spec's name. Never duplicate a
component because it appears in two phases — reuse the one node and point an edge back at it.
- Every FLOW step becomes an edge. Error and alternate paths are not optional.
- Two nodes get at most ONE edge between them. If the spec sends A→B and B→A, keep the
direction that carries the real outcome and drop the acknowledgement.
- Node `label` is the component name (1-3 words). Concrete detail (endpoint, method, \
status code, protocol, algorithm) goes in `subtitle` — never in the label.
- Every `decision` node needs 2+ outgoing edges, each with a branch label \
(yes/no, valid/expired).
- Edge `label`: at most 2 short words; omit it when the transition is obvious.

Structure:
- The spec's PHASES become numbered `groups` ("1. Login & Token Issuance"). Assign EVERY \
node to a group and give each group a distinct color.
- Pick a semantic `kind` and an `icon` for each node.
- Prefer edges between adjacent groups; avoid long jumps across the diagram.

Self-check before you answer: does every FLOW line in the spec appear as an edge? A \
multi-phase spec that produces fewer than 10 nodes means you dropped content."""

_SYSTEM_DIRECT = """You turn a description into a directed diagram graph.

- Cover the whole description, including failure and alternate paths — a flow with only \
the happy path is incomplete. 10-20 nodes is normal; 24 is the hard ceiling.
- Never invent product names, versions or vendors the user did not state; use generic \
labels ("Database", not "PostgreSQL").
- Node `label` is 1-3 words. Concrete detail (endpoint, method, status code, protocol) \
goes in `subtitle` — never in the label.
- Give each node a semantic `kind` and an `icon`. Every `decision` node needs 2+ outgoing \
edges with branch labels (yes/no, valid/expired).
- Group the flow into 3-5 numbered phase `groups` ("1. Login & Token Issuance") and assign \
EVERY node to one. Skip groups only for a genuinely simple linear flow.
- Edge `label`: at most 2 short words; omit it on obvious transitions."""

_SYSTEM_REPAIR = """You are correcting a diagram graph you produced. A validator found the \
problems listed below. Return the COMPLETE corrected graph — every node and edge, not just \
the fixes — keeping everything that was already right. Fix only what is listed, and stay \
within the spec: add nothing it does not contain."""


async def _ask(
    cfg: LLMConfig, system: str, human: str, stage: str, meter=None
) -> DiagramPlan | None:
    """One typed request, retried across structured-output methods before giving up."""
    for method in _METHODS:
        try:
            model = build_chat_model(cfg).with_structured_output(DiagramPlan, method=method)
            plan = await model.ainvoke(
                [("system", system), ("human", human)], config=meter_config(meter)
            )
        except Exception:
            logger.warning("%s failed via %s (model=%s)", stage, method, cfg.model, exc_info=True)
            continue
        if isinstance(plan, DiagramPlan) and plan.nodes:
            return plan
        logger.warning("%s returned an empty plan via %s (model=%s)", stage, method, cfg.model)
    return None


async def plan_from_text(
    message: str, llm_override: dict | None = None, spec: object | None = None, meter=None
) -> DiagramPlan | None:
    """Spec (preferred) or raw text → DiagramPlan. `spec` is a `DiagramSpec`; typed as
    `object` to keep this module free of a circular import with spec_llm."""
    cfg = resolve_config(llm_override, role="plan")
    raw_spec = getattr(spec, "raw", None)
    if not cfg.api_key or not (raw_spec or message.strip()):
        return None

    system = _SYSTEM_SPEC if raw_spec else _SYSTEM_DIRECT
    return await _ask(cfg, system, raw_spec or message, "planner", meter)


async def refine_plan(
    plan: DiagramPlan,
    brief: str,
    llm_override: dict | None = None,
    spec: object | None = None,
    meter=None,
) -> DiagramPlan | None:
    """One targeted repair pass driven by the validator's findings. None on any failure —
    the caller keeps the original plan, so a repair can never make the run worse."""
    cfg = resolve_config(llm_override, role="plan")
    if not cfg.api_key or not brief.strip():
        return None

    raw_spec = getattr(spec, "raw", None)
    human = (
        (f"SPEC:\n{raw_spec}\n\n" if raw_spec else "")
        + f"CURRENT GRAPH:\n{plan.model_dump_json(exclude_none=True)}\n\n"
        + f"PROBLEMS TO FIX:\n{brief}"
    )
    return await _ask(cfg, _SYSTEM_REPAIR, human, "plan repair", meter)
