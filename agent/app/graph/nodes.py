"""LangGraph nodes: Router → Planner → Drawer → Critic.

Step 1 makes the **SQL → ERD** path real and deterministic (no LLM): the Router
detects a SQL schema and parses it, and the Drawer lays out an ERD from the parsed
tables. The `text` path (freeform description) is still a stub — it becomes the first
Claude tool-calling node in a later step (PLAN.md §5).
"""
from __future__ import annotations

from app.graph.layout import build_erd_actions
from app.graph.state import AgentState
from app.schema import AgentAction, Shape
from app.tools.parse_sql import looks_like_sql, parse_sql


def router(state: AgentState) -> AgentState:
    """Classify the input and, when structured, parse it into a schema."""
    text = state.get("payload") or state.get("user_message", "")
    forced = state.get("input_kind")

    if forced == "sql" or (forced is None and looks_like_sql(text)):
        parsed = parse_sql(text)
        if not parsed.is_empty:
            return {"input_kind": "sql", "parsed": parsed}

    return {"input_kind": forced or "text", "parsed": None}


def planner(state: AgentState) -> AgentState:
    """Turn intent + parsed input into a plan. Touches no shapes."""
    parsed = state.get("parsed")
    if parsed and parsed.tables:
        return {
            "plan": {
                "nodes": [{"id": t.name, "label": t.name} for t in parsed.tables],
                "edges": [
                    {"from": r.from_table, "to": r.to_table} for r in parsed.relations
                ],
                "notes": "deterministic ERD from SQL",
            }
        }

    # text path (stub until the LLM planner lands)
    msg = state.get("user_message", "").strip()
    return {
        "plan": {
            "nodes": [{"id": "a", "label": "Start"}, {"id": "b", "label": msg[:24] or "Step"}],
            "edges": [{"from": "a", "to": "b"}],
            "notes": "phase-0 stub plan",
        }
    }


def drawer(state: AgentState) -> AgentState:
    """Turn the plan into concrete canvas actions (streamed to the client)."""
    parsed = state.get("parsed")
    if parsed and parsed.tables:
        return {"actions": build_erd_actions(parsed)}

    # text path (stub)
    label = (state.get("user_message", "") or "Step")[:24]
    actions = [
        AgentAction(type="create", shape=Shape(id="a", type="geo", x=100, y=100, w=160, h=80, text="Start")),
        AgentAction(type="create", shape=Shape(id="b", type="geo", x=360, y=100, w=160, h=80, text=label)),
        AgentAction(type="create", shape=Shape(id="edge-ab", type="arrow", x=260, y=140, from_id="a", to_id="b")),
    ]
    return {"actions": actions}


def critic(state: AgentState) -> AgentState:
    """Inspect the result and decide whether a refine pass is needed.

    Step-1: no vision check yet → always 'no issues'. Once wired, it reads the
    screenshot + shape data and flags overlaps / missing steps (PLAN.md §5).
    """
    return {
        "critique": {"has_issues": False, "issues": []},
        "iterations": state.get("iterations", 0) + 1,
    }
