"""Wire the Router → Specifier → Planner → Drawer → Critic graph with a bounded refine loop.

Runs on Canvo's own `engine.Graph` (see engine.py) — no orchestration framework.

    router → editor → specifier → planner → drawer → critic ─┬─(refine)→ drawer
                                                             └─(else)──→ END

The Editor runs first and only matters for a follow-up: given the diagram already on
screen, it turns the prompt into changes and hands the planner a finished plan, which the
Specifier and Planner then skip. A first prompt, or one the Editor reads as being about a
different subject, falls through to the full create path.

The Specifier is a no-op for SQL/OpenAPI input (already structured) and when no LLM key
is configured, so the deterministic paths keep their single-pass cost.
"""

from __future__ import annotations

from app.graph import nodes
from app.graph.engine import END, Graph
from app.graph.state import AgentState
from app.guardrails import MAX_ITERATIONS


def _should_refine(state: AgentState) -> str:
    """Route the Critic's verdict. The Critic already applied the iteration cap when it
    set `needs_refine`, so we just honour it (and re-check the cap defensively)."""
    critique = state.get("critique") or {}
    if critique.get("needs_refine") and state.get("iterations", 0) < MAX_ITERATIONS:
        return "refine"
    return "done"


def build_graph() -> Graph:
    g = Graph()
    g.add_node("router", nodes.router)
    g.add_node("editor", nodes.editor)
    g.add_node("specifier", nodes.specifier)
    g.add_node("planner", nodes.planner)
    g.add_node("drawer", nodes.drawer)
    g.add_node("critic", nodes.critic)

    g.set_entry("router")
    g.add_edge("router", "editor")
    g.add_edge("editor", "specifier")
    g.add_edge("specifier", "planner")
    g.add_edge("planner", "drawer")
    g.add_edge("drawer", "critic")
    g.add_conditional("critic", _should_refine, {"refine": "drawer", "done": END})

    return g


# Built once at import; reused per request (nodes are stateless — state is per-call).
graph = build_graph()
