"""LangGraph nodes: Planner → Drawer → Critic.

These are Phase-0 STUBS. They produce a tiny hardcoded diagram so the
end-to-end pipeline (client → service → streamed actions → canvas) works
before any LLM is wired in.

TODO(canvo): replace each body with Claude tool-calling (see PLAN.md §5):
  - planner: intent + canvas_context → structured Plan          (Haiku 4.5)
  - drawer:  Plan → AgentAction[] via typed tool schemas        (Sonnet 5)
  - critic:  screenshot + shapes → Critique (vision-grounded)   (Sonnet 5)
"""
from __future__ import annotations

from app.graph.state import AgentState
from app.schema import AgentAction, Shape


def planner(state: AgentState) -> AgentState:
    """Turn intent + current canvas into a structured plan. Touches no shapes."""
    msg = state.get("user_message", "").strip()
    plan = {
        "nodes": [
            {"id": "a", "label": "Start"},
            {"id": "b", "label": msg[:24] or "Step"},
        ],
        "edges": [{"from": "a", "to": "b"}],
        "notes": "phase-0 stub plan",
    }
    return {"plan": plan}


def drawer(state: AgentState) -> AgentState:
    """Turn the plan into concrete canvas actions (streamed to the client)."""
    label = (state.get("user_message", "") or "Step")[:24]
    actions = [
        AgentAction(type="create", shape=Shape(id="a", type="geo", x=100, y=100, w=160, h=80, text="Start")),
        AgentAction(type="create", shape=Shape(id="b", type="geo", x=360, y=100, w=160, h=80, text=label)),
        AgentAction(type="create", shape=Shape(id="edge-ab", type="arrow", x=260, y=140)),
    ]
    return {"actions": actions}


def critic(state: AgentState) -> AgentState:
    """Inspect the result and decide whether a refine pass is needed.

    Phase-0: no real vision check yet → always reports 'no issues'. Once wired,
    this reads the screenshot + shape data and flags overlaps / missing steps.
    """
    return {
        "critique": {"has_issues": False, "issues": []},
        "iterations": state.get("iterations", 0) + 1,
    }
