"""Drive Canvo's real graph for a Tier-1 golden case. Test-only — see EVAL-PLAN.md §4/§8.

Every case runs actual production code: `app.graph.build.graph`, `apply_ops`, `sanitize`,
`validate`, `drawer`, `layout.py`, `route_arrows`, `critique.py`. Nothing here reimplements
a node. The one LLM call each path would otherwise make (`propose_edit`, `write_spec`,
`plan_from_text`) is replaced by a frozen, monkeypatched return value — the "recorded
response" a golden case runs against, except Tier 1's response is engineered by hand rather
than played back from a fixture file (that's Tier 2). Everything downstream is real.

A case is a JSON file under `cases/`, named `<category>-<slug>.json`. `category` selects
which `run_*_case` builds the initial state; `expect` is checked by `check_properties`.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from app.eval.record import RunRecord, record_from_run
from app.graph import nodes
from app.graph.build import graph
from app.graph.edit_llm import DiagramEdit, EditOp
from app.graph.planner_llm import DiagramPlan
from app.graph.spec_llm import parse_spec
from app.schema import CanvasContext

CASES_DIR = Path(__file__).parent / "cases"

# Geometry issues the composition/routing pipeline can produce, that a refine is meant to
# clear. `arrow_crossing` / `label_collision` are reported but not refine triggers (see
# critique.py) — a case that wants zero of those too should say so via `must_not_raise_issue`.
_BLOCKING_GEOMETRY = {"overlap", "container_overflow", "dangling_arrow"}


def load_cases(category: str) -> list[dict[str, Any]]:
    """Every `<category>-*.json` fixture, sorted for a stable, diffable test order."""
    files = sorted(CASES_DIR.glob(f"{category}-*.json"))
    cases = []
    for f in files:
        case = json.loads(f.read_text())
        assert case["id"] == f.stem, f"case id must match its filename: {f.name}"
        assert case["category"] == category, f"{f.name} is filed under '{category}'"
        cases.append(case)
    return cases


def _base_state(**over: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "user_message": "",
        "payload": None,
        "canvas_context": CanvasContext(),
        "vision_enabled": False,  # Tier 1 is offline — see EVAL-PLAN.md §4
        "spec_enabled": True,
        "input_kind": None,
        "base_plan": None,
        "layout_params": {"gap_scale": 1.0},
        "iterations": 0,
        "cost_usd": 0.0,
    }
    state.update(over)
    return state


async def _drive(state: dict[str, Any]) -> tuple[list[dict], dict[str, float], float]:
    """Walk the real graph from `state`'s entry, collecting what `record_from_run` needs.

    Mirrors `main.py`'s `/agent/stream` handler: `passes` collects every critic visit (the
    state only keeps the last one), `stage_ms` sums per-node time across repeats (the
    drawer runs more than once on a refine).
    """
    passes: list[dict] = []
    stage_ms: dict[str, float] = {}

    def timed(node: str, elapsed: float) -> None:
        stage_ms[node] = round(stage_ms.get(node, 0.0) + elapsed, 1)

    started = time.perf_counter()
    async for node, out in graph.astream(state, timed):
        if node == "critic" and out.get("critique"):
            passes.append(out["critique"])
    total_ms = (time.perf_counter() - started) * 1000
    return passes, stage_ms, total_ms


def _record(
    state: dict[str, Any], passes: list[dict], stage_ms: dict, total_ms: float
) -> RunRecord:
    shapes = len(state.get("actions") or [])
    return record_from_run(
        state,
        outcome="completed",
        passes=passes,
        stage_ms=stage_ms,
        total_ms=total_ms,
        shapes=shapes,
    )


def run_sql_case(case: dict, monkeypatch) -> tuple[dict, RunRecord]:
    state = _base_state(payload=case["input"]["ddl"], input_kind="sql")
    passes, stage_ms, total_ms = asyncio.run(_drive(state))
    return state, _record(state, passes, stage_ms, total_ms)


def run_openapi_case(case: dict, monkeypatch) -> tuple[dict, RunRecord]:
    state = _base_state(payload=case["input"]["spec"], input_kind="openapi")
    passes, stage_ms, total_ms = asyncio.run(_drive(state))
    return state, _record(state, passes, stage_ms, total_ms)


def run_edit_case(case: dict, monkeypatch) -> tuple[dict, RunRecord]:
    """`ops` are frozen, not proposed: this tests `apply_ops`/`sanitize`/`validate` and the
    downstream drawer+critic, not whether an LLM reads a request correctly (that's Tier 2).
    """
    inp = case["input"]
    base_plan = DiagramPlan(**inp["base_plan"])
    edit = DiagramEdit(
        intent=inp.get("intent", "edit"),
        ops=[EditOp(**o) for o in inp.get("ops", [])],
        summary=inp.get("summary", ""),
        reply=inp.get("reply", ""),
    )

    async def fake_propose_edit(*_args: Any, **_kwargs: Any) -> DiagramEdit:
        return edit

    monkeypatch.setattr(nodes, "propose_edit", fake_propose_edit)
    state = _base_state(
        input_kind="text",
        payload=inp.get("request", "(frozen edit fixture — propose_edit is stubbed)"),
        base_plan=base_plan,
    )
    passes, stage_ms, total_ms = asyncio.run(_drive(state))
    return state, _record(state, passes, stage_ms, total_ms)


def run_create_case(case: dict, monkeypatch) -> tuple[dict, RunRecord]:
    """The plan is frozen, standing in for what the Planner LLM would have returned — this
    tests `sanitize`/`validate`/drawer/composition/routing/critic, not the model call.
    """
    inp = case["input"]
    plan = DiagramPlan(**inp["plan"])
    spec = parse_spec(inp["spec_markdown"]) if inp.get("spec_markdown") else None

    async def fake_write_spec(*_args: Any, **_kwargs: Any):
        return spec

    async def fake_plan_from_text(*_args: Any, **_kwargs: Any) -> DiagramPlan:
        return plan

    monkeypatch.setattr(nodes, "write_spec", fake_write_spec)
    monkeypatch.setattr(nodes, "plan_from_text", fake_plan_from_text)
    state = _base_state(
        input_kind="text",
        payload=inp.get("request", "(frozen create fixture — the planner call is stubbed)"),
        spec_enabled=spec is not None,
    )
    passes, stage_ms, total_ms = asyncio.run(_drive(state))
    return state, _record(state, passes, stage_ms, total_ms)


_RUNNERS = {
    "sql": run_sql_case,
    "openapi": run_openapi_case,
    "edit": run_edit_case,
    "create": run_create_case,
}


def run_case(case: dict, monkeypatch) -> tuple[dict, RunRecord]:
    return _RUNNERS[case["category"]](case, monkeypatch)


def check_properties(case: dict, state: dict) -> list[str]:
    """Every claim EVAL-PLAN.md §4 says a golden case should hold, checked against what the
    run actually produced. Returns violation messages; empty means the case passed.

    Geometry ("clean") is judged from `state["critique"]` — the LAST critic pass, which the
    engine merges into state as it goes. An earlier pass having an overlap is not a
    violation; that is exactly what the refine loop exists to fix. Checking every pass
    instead of the last one would fail every case that needed a refine to get clean.
    """
    exp = case.get("expect", {})
    problems: list[str] = []

    actions = state.get("actions") or []
    box_ids = {a.shape.id for a in actions if a.shape and a.shape.type in ("geo", "container")}
    arrows = [a.shape for a in actions if a.shape and a.shape.type == "arrow"]
    n_boxes = sum(1 for a in actions if a.shape and a.shape.type == "geo")
    n_edges = len(arrows)

    for want in exp.get("must_contain", []):
        if want not in box_ids:
            problems.append(f"missing required shape '{want}'")
    for forbidden in exp.get("must_not_contain", []):
        if forbidden in box_ids:
            problems.append(f"forbidden shape '{forbidden}' is present")
    for pair in exp.get("must_connect", []):
        a, b = pair
        if not any({ar.from_id, ar.to_id} == {a, b} for ar in arrows):
            problems.append(f"missing connection {a} <-> {b}")

    if (lo := exp.get("nodes_min")) is not None and n_boxes < lo:
        problems.append(f"expected >= {lo} nodes, got {n_boxes}")
    if (hi := exp.get("nodes_max")) is not None and n_boxes > hi:
        problems.append(f"expected <= {hi} nodes, got {n_boxes}")
    if (lo := exp.get("edges_min")) is not None and n_edges < lo:
        problems.append(f"expected >= {lo} edges, got {n_edges}")
    if (hi := exp.get("edges_max")) is not None and n_edges > hi:
        problems.append(f"expected <= {hi} edges, got {n_edges}")

    final_critique = state.get("critique") or {}
    geo_issue_kinds = {i["kind"] for i in final_critique.get("issues", [])}
    if exp.get("clean", True):
        if final_critique.get("needs_refine"):
            problems.append("final critic pass still wants a refine")
        if hit := geo_issue_kinds & _BLOCKING_GEOMETRY:
            problems.append(f"geometry issues present in the final run: {sorted(hit)}")

    refines = max(0, int(state.get("iterations", 0) or 0) - 1)
    if (hi := exp.get("max_refines")) is not None and refines > hi:
        problems.append(f"needed {refines} refine pass(es), budget was {hi}")
    if (lo := exp.get("min_refines")) is not None and refines < lo:
        problems.append(
            f"expected >= {lo} refine pass(es) (this case is meant to overlap first), got {refines}"
        )

    report = state.get("plan_report") or {}
    issue_kinds = {i.get("kind") for i in report.get("issues", [])} | geo_issue_kinds
    blocking = sum(1 for i in report.get("issues", []) if i.get("severity") == "error")
    blocking_max = exp.get("blocking_issues_max", 0)
    if blocking > blocking_max:
        problems.append(f"{blocking} blocking validator issue(s), budget was {blocking_max}")
    for kind in exp.get("must_raise_issue", []):
        if kind not in issue_kinds:
            problems.append(f"expected issue kind '{kind}' to be raised, it wasn't")

    repairs = len(report.get("fixes") or [])
    if (lo := exp.get("min_repairs")) is not None and repairs < lo:
        problems.append(f"expected >= {lo} repair(s), got {repairs}")
    if (hi := exp.get("max_repairs")) is not None and repairs > hi:
        problems.append(f"expected <= {hi} repair(s), got {repairs}")

    if (want := exp.get("intent")) is not None:
        got = report.get("intent") or ("answer" if state.get("answered") else None)
        if got != want:
            problems.append(f"expected intent '{want}', got '{got}'")

    if (want := exp.get("reply_contains")) is not None:
        if want.lower() not in (state.get("reply") or "").lower():
            problems.append(f"reply did not mention '{want}': {state.get('reply')!r}")

    if (want := exp.get("rejected_contains")) is not None:
        rejected = " | ".join(report.get("rejected") or [])
        if want.lower() not in rejected.lower():
            problems.append(f"rejected ops did not mention '{want}': {rejected!r}")

    return problems
