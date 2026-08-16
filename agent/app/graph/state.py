"""LangGraph state for the Planner → Drawer → Critic graph.

The whole run is carried in this state object. Each node returns a partial
update, which LangGraph merges in.
"""

from __future__ import annotations

from typing import TypedDict

from app.graph.planner_llm import DiagramPlan
from app.schema import AgentAction, CanvasContext
from app.tools.parse_openapi import ParsedAPI
from app.tools.parse_sql import ParsedSchema


class Plan(TypedDict, total=False):
    nodes: list[dict]
    edges: list[dict]
    groups: list[dict]  # only the freeform path sets this (LLM planner)
    notes: str


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
    llm_override: dict | None  # per-request BYOK/model override (never persisted)
    # set by the Router
    input_kind: str  # "text" | "sql" | "openapi" | "code"
    parsed: ParsedSchema | None
    parsed_api: ParsedAPI | None
    llm_plan: DiagramPlan | None
    # produced by the graph
    plan: Plan | None
    actions: list[AgentAction]
    critique: Critique | None
    layout_params: dict  # {"gap_scale": float} — the Critic tunes this to fix crowding
    # loop control / accounting
    iterations: int
    cost_usd: float
