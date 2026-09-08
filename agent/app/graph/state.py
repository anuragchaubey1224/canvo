"""LangGraph state for the Planner → Drawer → Critic graph.

The whole run is carried in this state object. Each node returns a partial
update, which LangGraph merges in.
"""

from __future__ import annotations

from typing import TypedDict

from app.graph.planner_llm import DiagramPlan
from app.graph.spec_llm import DiagramSpec
from app.schema import AgentAction, CanvasContext
from app.tools.parse_openapi import ParsedAPI
from app.tools.parse_sql import ParsedSchema


class Plan(TypedDict, total=False):
    nodes: list[dict]
    edges: list[dict]
    groups: list[dict]  # only the freeform path sets this (LLM planner)
    notes: str


class PlanReportDict(TypedDict, total=False):
    """What the validator found, in a shape the SSE layer can hand to the client."""

    nodes: int
    edges: int
    groups: int
    issues: list[dict]  # [{kind, severity, message}]
    fixes: list[str]  # deterministic repairs applied before validation
    repaired: bool  # did an LLM repair pass run and improve the plan?
    degraded: str  # non-empty when a stage failed and a fallback drew the diagram
    # Follow-up edits: what the request was read as, and what actually changed.
    intent: str  # "create" | "edit" | "replace"
    applied: list[str]
    rejected: list[str]
    summary: str


class Critique(TypedDict, total=False):
    has_issues: bool  # anything worth reporting
    needs_refine: bool  # should the graph loop back to the Drawer?
    issues: list[dict]  # [{kind, severity, message, shape_ids}]
    source: str  # "geometry" | "geometry+vision"
    summary: str  # one-line human summary
    gap_scale: float  # spacing scale this critique judged


class AgentState(TypedDict, total=False):
    # inputs
    user_message: str
    payload: str | None
    canvas_context: CanvasContext
    vision_enabled: bool  # run the vision Critic pass (needs an LLM key)
    spec_enabled: bool  # run the Spec Writer stage before planning (needs an LLM key)
    llm_override: dict | None  # per-request BYOK/model override (never persisted)
    # set by the Router
    input_kind: str  # "text" | "sql" | "openapi" | "code"
    parsed: ParsedSchema | None
    parsed_api: ParsedAPI | None
    # the diagram already on screen, loaded from the session — what a follow-up edits
    base_plan: DiagramPlan | None
    # set when the prompt was a question: the graph answers and draws nothing
    answered: bool
    reply: str
    # set by the Spec Writer (freeform text only)
    spec: DiagramSpec | None
    llm_plan: DiagramPlan | None
    # produced by the graph
    plan: Plan | None
    plan_report: PlanReportDict | None
    actions: list[AgentAction]
    critique: Critique | None
    layout_params: dict  # {"gap_scale": float} — the Critic tunes this to fix crowding
    # loop control / accounting
    iterations: int
    cost_usd: float
    # Set true when a discretionary model call (the plan repair pass, the vision Critic)
    # was skipped because the run had already spent its per-run cost cap. A capped run
    # still returns a diagram — it just misses the extras — so this flag is what keeps it
    # from looking identical to a clean one.
    budget_capped: bool
    # Token/cost accounting for this run — an app.usage.UsageMeter, or absent in tests
    # that stub the model. Typed loosely to keep the state module import-free.
    meter: object
