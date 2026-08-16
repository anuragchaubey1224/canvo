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


class Plan(TypedDict):
    nodes: list[dict]
    edges: list[dict]
    notes: str


class Critique(TypedDict):
    has_issues: bool
    issues: list[str]


class AgentState(TypedDict, total=False):
    # inputs
    user_message: str
    payload: str | None
    canvas_context: CanvasContext
    # set by the Router
    input_kind: str  # "text" | "sql" | "openapi" | "code"
    parsed: ParsedSchema | None
    parsed_api: ParsedAPI | None
    llm_plan: DiagramPlan | None
    # produced by the graph
    plan: Plan | None
    actions: list[AgentAction]
    critique: Critique | None
    # loop control / accounting
    iterations: int
    cost_usd: float
