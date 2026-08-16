"""LangGraph state for the Planner → Drawer → Critic graph.

The whole run is carried in this state object. Each node returns a partial
update, which LangGraph merges in.
"""
from __future__ import annotations

from typing import Optional, TypedDict

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
    payload: Optional[str]
    canvas_context: CanvasContext
    # set by the Router
    input_kind: str  # "text" | "sql" | "openapi" | "code"
    parsed: Optional[ParsedSchema]
    parsed_api: Optional[ParsedAPI]
    # produced by the graph
    plan: Optional[Plan]
    actions: list[AgentAction]
    critique: Optional[Critique]
    # loop control / accounting
    iterations: int
    cost_usd: float
