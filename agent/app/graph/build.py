"""Wire the Router → Planner → Drawer → Critic graph with a bounded refine loop.

START → router → planner → drawer → critic ─┬─(issues & iters<MAX)→ drawer  (refine)
                                            └─(else)──────────────→ END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph import nodes
from app.graph.state import AgentState

MAX_ITERS = 3  # loop guard — see guardrails.py / PLAN.md §6c


def _should_refine(state: AgentState) -> str:
    critique = state.get("critique")
    has_issues = bool(critique and critique.get("has_issues"))
    if has_issues and state.get("iterations", 0) < MAX_ITERS:
        return "refine"
    return "done"


def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("router", nodes.router)
    builder.add_node("planner", nodes.planner)
    builder.add_node("drawer", nodes.drawer)
    builder.add_node("critic", nodes.critic)

    builder.add_edge(START, "router")
    builder.add_edge("router", "planner")
    builder.add_edge("planner", "drawer")
    builder.add_edge("drawer", "critic")
    builder.add_conditional_edges("critic", _should_refine, {"refine": "drawer", "done": END})

    return builder.compile()


# Compiled once at import; reused per request.
graph = build_graph()
