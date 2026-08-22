"""Graph nodes: Router → Specifier → Planner → Drawer → Critic.

Real paths:
  - SQL DDL        → ERD            (parse_sql + build_erd_actions)  · deterministic
  - OpenAPI/Swagger → API surface   (parse_openapi + build_api_actions) · deterministic
  - freeform text  → spec → node/edge graph (Spec Writer + LLM planner + layout) · needs a key

The freeform path is two LLM stages, not one: the **Specifier** turns a vague request into
an explicit spec (components, flow steps, phases, and the assumptions it had to make), then
the **Planner** maps that spec onto a graph. Between them sits a deterministic validator —
structural slips are repaired in code, content gaps buy exactly one targeted repair call.

The Critic then runs two passes: a deterministic geometry check (overlaps / dangling
arrows) that reliably drives the bounded refine loop, and a best-effort vision pass (an
LLM looks at a rendered PNG) that catches the fuzzy, semantic layout problems.
"""

from __future__ import annotations

import logging

from app.graph.apply_ops import apply_ops
from app.graph.critic_vision import critique_image
from app.graph.critique import analyze_geometry, geometry_summary
from app.graph.edit_llm import propose_edit
from app.graph.layout import build_api_actions, build_erd_actions, build_graph_actions
from app.graph.planner_llm import plan_from_text, refine_plan
from app.graph.route import route_arrows
from app.graph.spec_llm import spec_to_plan, write_spec
from app.graph.state import AgentState, Critique, PlanReportDict
from app.graph.validate_plan import repair_brief, sanitize, validate
from app.guardrails import MAX_ITERATIONS
from app.schema import AgentAction, Shape
from app.tools.parse_openapi import looks_like_openapi, parse_openapi
from app.tools.parse_sql import looks_like_sql, parse_sql

logger = logging.getLogger(__name__)

# Below this, a request is a label rather than a description — a spec pass would invent
# more than it extracts, so we go straight to the planner.
_MIN_SPEC_CHARS = 24

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


async def editor(state: AgentState) -> AgentState:
    """Read a follow-up prompt as changes to the diagram already on screen.

    Only runs when there IS one. On success it hands the planner a finished plan and the
    Specifier and Planner both step aside — a follow-up is one LLM call, not three, and
    skips the Spec Writer entirely.

    Every failure path leaves the diagram alone rather than guessing: no key, a failed
    call, or ops that all get rejected all fall through to... nothing. `base_plan` stays
    the plan, and the caller sees why in the trace.
    """
    if state.get("input_kind") != "text":
        return {}
    base = state.get("base_plan")
    if not base or not base.nodes:
        return {}

    request = (state.get("payload") or state.get("user_message") or "").strip()
    if not request:
        return {}

    edit = await propose_edit(base, request, state.get("llm_override"), state.get("meter"))
    if edit is None:
        logger.warning("edit stage failed; falling through to a fresh generation")
        return {}
    if edit.intent == "replace":
        # The request is about something else. Drop the context and let the create path
        # run, rather than forcing unrelated ops onto an unrelated diagram.
        return {"base_plan": None}
    if edit.intent == "answer":
        # A question, not an instruction. Redrawing an unchanged diagram would throw away
        # the user's camera and reveal nothing, so the graph stops here.
        return {"answered": True, "reply": edit.reply.strip() or "No change needed."}

    result = apply_ops(base, edit.ops)

    if not result.plan.nodes:
        # An edit that empties the diagram is a mistake, not an instruction.
        logger.warning("edit would have left an empty diagram; keeping the previous one")
        result = apply_ops(base, [])
        result.rejected.append("that would have removed the whole diagram")

    # Sanitize/validate whichever plan is actually kept — computing these before the empty
    # check meant a refused edit reported the discarded plan's fixes and issues (e.g.
    # "the plan has no nodes") against a diagram that, on screen, had neither problem.
    fixes = sanitize(result.plan)
    report = validate(result.plan)

    plan_report: PlanReportDict = {
        "nodes": len(result.plan.nodes),
        "edges": len(result.plan.edges),
        "groups": len(result.plan.groups),
        "issues": [
            {"kind": i.kind, "severity": i.severity, "message": i.message} for i in report.issues
        ],
        "fixes": fixes,
        "repaired": False,
        "degraded": "",
        "intent": "edit",
        "applied": result.applied,
        "rejected": result.rejected,
        "summary": edit.summary or "",
    }
    return {
        "llm_plan": result.plan,
        "plan_report": plan_report,
        "plan": {
            "nodes": [
                {"id": n.id, "label": n.label, "kind": n.kind, "group": n.group}
                for n in result.plan.nodes
            ],
            "edges": [{"from": e.source, "to": e.target} for e in result.plan.edges],
            "groups": [{"id": g.id, "label": g.label} for g in result.plan.groups],
            "notes": "edited the existing diagram",
        },
    }


async def specifier(state: AgentState) -> AgentState:
    """Freeform text → an explicit diagram spec. No-op on every other path.

    SQL and OpenAPI inputs are already specifications, so they skip this entirely — the
    stage exists purely to give vague prose the structure the planner needs.
    """
    if state.get("llm_plan"):
        return {}  # the Editor already produced a plan; there is nothing to specify
    if state.get("input_kind") != "text" or not state.get("spec_enabled", True):
        return {}

    text = (state.get("payload") or state.get("user_message") or "").strip()
    if len(text) < _MIN_SPEC_CHARS:
        return {}

    spec = await write_spec(text, state.get("llm_override"), state.get("meter"))
    return {"spec": spec} if spec else {}


async def planner(state: AgentState) -> AgentState:
    """Turn intent + parsed input into a plan. Touches no shapes."""
    if state.get("llm_plan"):
        return {}  # an edit already settled what to draw
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
    spec = state.get("spec")
    text = (state.get("payload") or state.get("user_message") or "").strip()
    override = state.get("llm_override")
    if text or spec:
        llm_plan = await plan_from_text(text, override, spec=spec, meter=state.get("meter"))
        degraded = ""
        if llm_plan is None and spec is not None:
            # The planner call failed, but the spec already names every component, step and
            # phase — draw that rather than the two-box stub. The user gets their diagram;
            # the message says plainly that it came the cheap way.
            llm_plan = spec_to_plan(spec)
            if llm_plan is not None:
                degraded = "planner call failed — drew the spec directly"
                logger.warning("planner unavailable; built the diagram from the spec")
        if llm_plan:
            fixes = sanitize(llm_plan)
            report = validate(llm_plan, spec)
            repaired = False

            # One repair pass, and only for content the validator can name. We keep the
            # result only if it strictly reduces the blocking issues, so a bad repair
            # can never make the diagram worse than the first attempt.
            if report.blocking:
                candidate = await refine_plan(
                    llm_plan,
                    repair_brief(report.blocking),
                    override,
                    spec=spec,
                    meter=state.get("meter"),
                )
                if candidate:
                    candidate_fixes = sanitize(candidate)
                    candidate_report = validate(candidate, spec)
                    if len(candidate_report.blocking) < len(report.blocking):
                        llm_plan, report, repaired = candidate, candidate_report, True
                        fixes += candidate_fixes

            plan_report: PlanReportDict = {
                "nodes": len(llm_plan.nodes),
                "edges": len(llm_plan.edges),
                "groups": len(llm_plan.groups),
                "issues": [
                    {"kind": i.kind, "severity": i.severity, "message": i.message}
                    for i in report.issues
                ],
                "fixes": fixes,
                "repaired": repaired,
                "degraded": degraded,
                "intent": "create",
                "applied": [],
                "rejected": [],
                "summary": "",
            }
            return {
                "llm_plan": llm_plan,
                "plan_report": plan_report,
                "plan": {
                    "nodes": [
                        {"id": n.id, "label": n.label, "kind": n.kind, "group": n.group}
                        for n in llm_plan.nodes
                    ],
                    "edges": [{"from": e.source, "to": e.target} for e in llm_plan.edges],
                    "groups": [{"id": g.id, "label": g.label} for g in llm_plan.groups],
                    "notes": "LLM plan from spec" if spec else "LLM plan from text",
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
        vc = await critique_image(actions, context=context, meter=state.get("meter"))
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
