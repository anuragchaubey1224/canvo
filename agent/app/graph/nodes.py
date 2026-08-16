"""LangGraph nodes: Router → Planner → Drawer → Critic.

Real paths:
  - SQL DDL        → ERD            (parse_sql + build_erd_actions)  · deterministic
  - OpenAPI/Swagger → API surface   (parse_openapi + build_api_actions) · deterministic
  - freeform text  → node/edge graph (LLM planner + build_graph_actions) · needs an LLM key

The Critic runs two passes: a deterministic geometry check (overlaps / dangling arrows)
that reliably drives the bounded refine loop, and a best-effort vision pass (an LLM looks
at a rendered PNG of the diagram) that catches the fuzzy, semantic layout problems.
"""

from __future__ import annotations

from app.graph.critic_vision import critique_image
from app.graph.critique import analyze_geometry, geometry_summary
from app.graph.layout import build_api_actions, build_erd_actions, build_graph_actions
from app.graph.planner_llm import plan_from_text
from app.graph.route import route_arrows
from app.graph.state import AgentState, Critique
from app.guardrails import MAX_ITERATIONS
from app.schema import AgentAction, Shape
from app.tools.parse_openapi import looks_like_openapi, parse_openapi
from app.tools.parse_sql import looks_like_sql, parse_sql

# How much the Critic widens the layout when it finds crowding. > any box-height/row-pitch
# ratio we hit in practice, so one refine usually clears the overlap; loop is capped anyway.
_GAP_BUMP = 1.5


def router(state: AgentState) -> AgentState:
    """Classify the input and, when structured, parse it."""
    text = state.get("payload") or state.get("user_message", "")
    forced = state.get("input_kind")

    if forced == "sql" or (forced is None and looks_like_sql(text)):
        parsed = parse_sql(text)
        if not parsed.is_empty:
            return {"input_kind": "sql", "parsed": parsed}

    if forced == "openapi" or (forced is None and looks_like_openapi(text)):
        api = parse_openapi(text)
        if not api.is_empty:
            return {"input_kind": "openapi", "parsed_api": api}

    return {"input_kind": forced or "text", "parsed": None}


async def planner(state: AgentState) -> AgentState:
    """Turn intent + parsed input into a plan. Touches no shapes."""
    parsed = state.get("parsed")
    if parsed and parsed.tables:
        return {
            "plan": {
                "nodes": [{"id": t.name, "label": t.name} for t in parsed.tables],
                "edges": [{"from": r.from_table, "to": r.to_table} for r in parsed.relations],
                "notes": "deterministic ERD from SQL",
            }
        }

    api = state.get("parsed_api")
    if api and api.groups:
        return {
            "plan": {
                "nodes": [{"id": g.name, "label": g.name} for g in api.groups],
                "edges": [{"from": "api-root", "to": g.name} for g in api.groups],
                "notes": "API surface from OpenAPI",
            }
        }

    # freeform text → LLM planner (structured output). Falls through to a stub if no key.
    text = (state.get("payload") or state.get("user_message") or "").strip()
    if text:
        llm_plan = await plan_from_text(text, state.get("llm_override"))
        if llm_plan:
            return {
                "llm_plan": llm_plan,
                "plan": {
                    "nodes": [
                        {"id": n.id, "label": n.label, "kind": n.kind, "group": n.group}
                        for n in llm_plan.nodes
                    ],
                    "edges": [{"from": e.source, "to": e.target} for e in llm_plan.edges],
                    "groups": [{"id": g.id, "label": g.label} for g in llm_plan.groups],
                    "notes": "LLM plan from text",
                },
            }

    return {
        "plan": {
            "nodes": [{"id": "a", "label": "Start"}, {"id": "b", "label": text[:24] or "Step"}],
            "edges": [{"from": "a", "to": "b"}],
            "notes": "stub plan (no LLM key or empty input)",
        }
    }


def drawer(state: AgentState) -> AgentState:
    """Turn the plan into concrete canvas actions (streamed to the client).

    Reads `layout_params.gap_scale` so a refine pass redraws with wider spacing.
    """
    scale = float((state.get("layout_params") or {}).get("gap_scale", 1.0))

    parsed = state.get("parsed")
    if parsed and parsed.tables:
        return {"actions": route_arrows(build_erd_actions(parsed, gap_scale=scale))}

    api = state.get("parsed_api")
    if api and api.groups:
        return {"actions": route_arrows(build_api_actions(api, gap_scale=scale))}

    llm_plan = state.get("llm_plan")
    if llm_plan and llm_plan.nodes:
        return {"actions": route_arrows(build_graph_actions(llm_plan, gap_scale=scale))}

    # stub (no LLM key / empty input)
    label = (state.get("payload") or state.get("user_message") or "Step")[:24]
    actions = [
        AgentAction(
            type="create", shape=Shape(id="a", type="geo", x=100, y=100, w=160, h=80, text="Start")
        ),
        AgentAction(
            type="create", shape=Shape(id="b", type="geo", x=360, y=100, w=160, h=80, text=label)
        ),
        AgentAction(
            type="create",
            shape=Shape(id="edge-ab", type="arrow", x=260, y=140, from_id="a", to_id="b"),
        ),
    ]
    return {"actions": actions}


async def critic(state: AgentState) -> AgentState:
    """Inspect the drawn diagram and decide whether a refine pass is worth it.

    Two passes:
      1. Geometry (always, deterministic) — overlaps / dangling arrows. Overlap is the
         reliable refine trigger; the lever we pull is `gap_scale` (widen the layout).
      2. Vision (once, first visit, needs a key) — an LLM looks at a rendered PNG and
         flags crowding / readability / tangled arrows the geometry pass can't see.

    A refine is requested only when a *spacing-fixable* problem is found and we're under
    the iteration cap, so the loop always converges.
    """
    actions = state.get("actions", [])
    iters = state.get("iterations", 0) + 1
    scale = float((state.get("layout_params") or {}).get("gap_scale", 1.0))

    report = analyze_geometry(actions)
    issues: list[dict] = [i.model_dump() for i in report.issues]
    source = "geometry"
    summary = geometry_summary(report)

    # Vision pass: only on the first visit (bounds cost/latency to one call per run).
    vision_says_crowded = False
    if iters == 1 and state.get("vision_enabled", True):
        context = state.get("user_message") or state.get("payload") or ""
        vc = await critique_image(actions, context=context)
        if vc is not None:
            source = "geometry+vision"
            for vi in vc.issues:
                issues.append(
                    {
                        "kind": f"vision:{vi.kind}",
                        "severity": "warning",
                        "message": vi.message,
                        "shape_ids": [],
                    }
                )
            if vc.summary:
                summary = vc.summary
            vision_says_crowded = vc.has_issues and any(
                vi.kind in ("overlap", "crowding") for vi in vc.issues
            )

    wants_more_space = report.has_overlap or vision_says_crowded
    needs_refine = wants_more_space and iters < MAX_ITERATIONS

    critique: Critique = {
        "has_issues": bool(issues),
        "needs_refine": needs_refine,
        "issues": issues,
        "source": source,
        "summary": summary,
        "gap_scale": scale,
    }
    updates: AgentState = {"critique": critique, "iterations": iters}
    if needs_refine:
        updates["layout_params"] = {"gap_scale": round(scale * _GAP_BUMP, 3)}
    return updates
