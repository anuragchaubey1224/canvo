"""Conversational editing — turn a follow-up prompt into changes to the diagram on screen.

Without this, every prompt was a fresh generation: "add cylinders where it makes sense"
had no diagram to add them to, so the model invented an unrelated one. The fix is to give
the model the current graph and ask for a **diff**, not a rewrite.

Why operations rather than a new `DiagramPlan`:

  - **No drift.** Asked to restate a 13-node graph with one change, a model quietly
    rewords labels, drops an edge, renames a phase. A list of ops can only do what it says.
  - **Cheap.** ~900 tokens in and ~250 out, against ~3,400/1,240 for a full generation, and
    it skips the Spec Writer entirely — a follow-up costs roughly a quarter of a create.
  - **Checkable.** An op naming an id that doesn't exist is rejected and reported, instead
    of silently becoming a new node.

The intent lives in the same response rather than in a separate classifier call: the model
is already holding the graph, so it is the best-placed thing to decide whether the request
is an edit of *this* diagram or a request for a different one.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.graph.planner_llm import DiagramPlan
from app.llm import resolve_config, structured_call

_OPS = (
    "add_node",
    "update_node",
    "remove_node",
    "add_edge",
    "update_edge",
    "remove_edge",
    "add_group",
    "update_group",
    "remove_group",
    "set_title",
)


class EditOp(BaseModel):
    """One change.

    Flat with optional fields rather than a discriminated union: models fill a single flat
    shape far more reliably through structured output, and the apply step validates what
    each op actually needs anyway.
    """

    op: Literal[
        "add_node",
        "update_node",
        "remove_node",
        "add_edge",
        "update_edge",
        "remove_edge",
        "add_group",
        "update_group",
        "remove_group",
        "set_title",
    ] = Field(description="which change to make")
    id: str | None = Field(default=None, description="node or group id this op targets")
    source: str | None = Field(default=None, description="edge source node id")
    target: str | None = Field(default=None, description="edge target node id")
    label: str | None = Field(default=None, description="new label (node, edge or group)")
    kind: str | None = Field(
        default=None,
        description=(
            "service | datastore | decision | client | external | queue | start | end | note"
        ),
    )
    subtitle: str | None = Field(default=None, description="node detail line")
    group: str | None = Field(default=None, description="id of the group the node belongs to")
    icon: str | None = Field(default=None, description="icon name")
    color: str | None = Field(default=None, description="group colour token")
    title: str | None = Field(default=None, description="new diagram title, for set_title")


class DiagramEdit(BaseModel):
    intent: Literal["edit", "replace", "answer"] = Field(
        description=(
            "'edit' to change the diagram shown; 'answer' when the user asked a question "
            "about it and nothing should change; 'replace' only when the request is about "
            "something else entirely and a new diagram should be drawn from scratch"
        )
    )
    ops: list[EditOp] = Field(
        default_factory=list,
        description="the changes, in order. Empty means nothing needs to change.",
    )
    summary: str = Field(default="", description="one short line describing what changed")
    reply: str = Field(
        default="",
        description="for intent='answer': the answer itself, two or three sentences",
    )


_SYSTEM = """You are editing a diagram that is already on the user's screen. You are given \
its graph and a request. Return the CHANGES, never a rewritten graph.

Rules:
- Use the EXACT ids from the graph. Never invent an id for something that already exists.
- Change only what was asked. Everything you don't mention stays as it is.
- One op per change. `update_node` only needs the fields that change.
- To turn boxes into cylinders/databases, that is `update_node` with kind='datastore'.
  Diamonds are kind='decision'. Both are chosen by kind, never by drawing anything.
- A new node usually needs a `group` too, or it will float outside every phase.
- If the request is already true of the diagram, return intent='edit' with no ops.

Use intent='answer' when the user is ASKING about the diagram rather than asking you to \
change it ("why is X there?", "what happens when the token expires?"). Put the answer in \
`reply`, two or three sentences, grounded in the graph above. Change nothing.

Set intent='replace' ONLY when the request is about a different subject altogether — a new
diagram, not a change to this one. Rewording, adding, removing, restyling, regrouping and \
relabelling are all 'edit', however large."""


def _compact(plan: DiagramPlan) -> str:
    """The graph as the model sees it. Small on purpose — this is the whole context."""
    lines = [f"TITLE: {plan.title or '(none)'}"]
    if plan.groups:
        lines.append("GROUPS:")
        lines += [f"  {g.id} = {g.label}" for g in plan.groups]
    lines.append("NODES:")
    for node in plan.nodes:
        bits = [
            f"kind={node.kind}" if node.kind else "",
            f"group={node.group}" if node.group else "",
        ]
        detail = f" — {node.subtitle}" if node.subtitle else ""
        lines.append(f"  {node.id} = {node.label}{detail} [{' '.join(b for b in bits if b)}]")
    lines.append("EDGES:")
    for edge in plan.edges:
        label = f" ({edge.label})" if edge.label else ""
        lines.append(f"  {edge.source} -> {edge.target}{label}")
    return "\n".join(lines)


async def propose_edit(
    plan: DiagramPlan, request: str, llm_override: dict | None = None, meter=None
) -> DiagramEdit | None:
    """Ask for a diff against `plan`. None when there's no key or the call fails, in which
    case the caller must leave the diagram alone rather than guess."""
    cfg = resolve_config(llm_override, role="plan")
    if not cfg.api_key or not request.strip() or not plan.nodes:
        return None

    human = f"CURRENT DIAGRAM:\n{_compact(plan)}\n\nREQUEST:\n{request.strip()}"
    return await structured_call(cfg, _SYSTEM, human, DiagramEdit, "diagram edit", meter)


__all__ = ["DiagramEdit", "EditOp", "propose_edit", "_OPS"]
