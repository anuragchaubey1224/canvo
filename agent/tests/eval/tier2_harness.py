"""Drive Canvo's real freeform graph for a Tier-2 case. See EVAL-PLAN.md §4, §7 (phase 03).

Tier 1 hand-writes the model's answer; Tier 2 plays back a *recorded* one. Everything
downstream of the model — `specifier`, `planner`, `sanitize`, `validate`, one `refine_plan`
pass, `apply_ops`, the drawer, the geometry critic, layout, routing — is real production
code, the same as Tier 1.

Two modes, chosen by `--record` (see `conftest.py`):

  - **replay** (default) — the three freeform entry points (`write_spec`, `plan_from_text`,
    `refine_plan`) and the edit entry point (`propose_edit`) are monkeypatched to return
    the objects saved under `responses/<case-id>.json`. No network. This is what CI runs.
  - **record** — those same entry points run for real against the live model, and their
    return values are captured to `responses/`. `tests/conftest.py` clears the provider
    key to keep the suite offline; `_load_real_env()` puts it back, and only here.

The **vision critic stays off** (`vision_enabled=False`), exactly as in Tier 1. Tier 2
measures the semantic spec→plan path — component recall, hallucination, structure,
assumptions. The vision pass is a layout signal the geometry critic already covers
deterministically, and recording it would mean a base64 PNG fixture that rots on any
layout change. Phase 04's judge is where the semantic-layout questions get asked.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from app.eval.record import RunRecord, record_from_run
from app.graph import nodes
from app.graph.build import graph
from app.graph.edit_llm import DiagramEdit
from app.graph.planner_llm import DiagramPlan
from app.graph.spec_llm import DiagramSpec
from app.schema import CanvasContext

CASES_DIR = Path(__file__).parent / "cases"
RESPONSES_DIR = Path(__file__).parent / "responses"

_KINDS = ("create", "edit", "question")

# Geometry issue kinds a refine is meant to clear (mirrors tests/eval/harness.py).
_BLOCKING_GEOMETRY = {"overlap", "container_overflow", "dangling_arrow"}

# Env vars tests/conftest.py strips; --record restores them from agent/.env.
_ENV_KEYS = (
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_SPEC_MODEL",
    "LLM_PLAN_MODEL",
    "LLM_VISION_MODEL",
    "LLM_BASE_URL",
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
)


# --- cases -----------------------------------------------------------------------------


def load_tier2_cases() -> list[dict[str, Any]]:
    """Every `tier2-*.json` under `cases/`, sorted for a stable, diffable test order."""
    cases = []
    for f in sorted(CASES_DIR.glob("tier2-*.json")):
        case = json.loads(f.read_text())
        assert case["id"] == f.stem, f"case id must match its filename: {f.name}"
        assert case["category"] == "tier2", f"{f.name}: category must be 'tier2'"
        assert case["kind"] in _KINDS, f"{f.name}: kind must be one of {_KINDS}"
        cases.append(case)
    return cases


# --- replay / record wiring ----------------------------------------------------------


def _install_replay(case: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    path = RESPONSES_DIR / f"{case['id']}.json"
    if not path.exists():
        pytest.fail(
            f"no recorded response for {case['id']}. Recording spends money — agree the "
            f"cost first (EVAL-PLAN.md §8), then:\n"
            f"    pytest tests/eval/test_tier2.py --record --record-only {case['id']}",
            pytrace=False,
        )
    calls = json.loads(path.read_text()).get("calls", {})

    async def fake_write_spec(*_a: Any, **_k: Any) -> DiagramSpec | None:
        d = calls.get("write_spec")
        return DiagramSpec(**d) if d else None

    async def fake_plan_from_text(*_a: Any, **_k: Any) -> DiagramPlan | None:
        d = calls.get("plan_from_text")
        return DiagramPlan(**d) if d else None

    async def fake_refine_plan(*_a: Any, **_k: Any) -> DiagramPlan | None:
        d = calls.get("refine_plan")
        return DiagramPlan(**d) if d else None

    async def fake_propose_edit(*_a: Any, **_k: Any) -> DiagramEdit | None:
        d = calls.get("propose_edit")
        return DiagramEdit(**d) if d else None

    monkeypatch.setattr(nodes, "write_spec", fake_write_spec)
    monkeypatch.setattr(nodes, "plan_from_text", fake_plan_from_text)
    monkeypatch.setattr(nodes, "refine_plan", fake_refine_plan)
    monkeypatch.setattr(nodes, "propose_edit", fake_propose_edit)


def _load_real_env() -> None:
    """Undo tests/conftest.py's key-clearing — for --record only. `dotenv_values` reads the
    file directly; only `load_dotenv` was neutered, so this still works."""
    import dotenv

    env_file = Path(__file__).resolve().parents[2] / ".env"  # agent/.env
    if not env_file.exists():
        pytest.fail(
            f"--record needs agent/.env with a provider key; {env_file} not found", pytrace=False
        )
    values = dotenv.dotenv_values(env_file)
    for key in _ENV_KEYS:
        if values.get(key):
            os.environ[key] = str(values[key])
    if not (os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")):
        pytest.fail(
            "--record: no OPENROUTER_API_KEY / ANTHROPIC_API_KEY in agent/.env", pytrace=False
        )


def _install_record(
    case: dict[str, Any], monkeypatch: pytest.MonkeyPatch, captured: dict[str, Any]
) -> None:
    _load_real_env()
    from app.graph import edit_llm, planner_llm, spec_llm

    real_write_spec = spec_llm.write_spec
    real_plan_from_text = planner_llm.plan_from_text
    real_refine_plan = planner_llm.refine_plan
    real_propose_edit = edit_llm.propose_edit

    async def rec_write_spec(*a: Any, **k: Any) -> DiagramSpec | None:
        r = await real_write_spec(*a, **k)
        if r is not None:
            captured["write_spec"] = r.model_dump(mode="json")
        return r

    async def rec_plan_from_text(*a: Any, **k: Any) -> DiagramPlan | None:
        r = await real_plan_from_text(*a, **k)
        if r is not None:
            captured["plan_from_text"] = r.model_dump(mode="json")
        return r

    async def rec_refine_plan(*a: Any, **k: Any) -> DiagramPlan | None:
        r = await real_refine_plan(*a, **k)
        if r is not None:
            captured["refine_plan"] = r.model_dump(mode="json")
        return r

    async def rec_propose_edit(*a: Any, **k: Any) -> DiagramEdit | None:
        r = await real_propose_edit(*a, **k)
        if r is not None:
            captured["propose_edit"] = r.model_dump(mode="json")
        return r

    monkeypatch.setattr(nodes, "write_spec", rec_write_spec)
    monkeypatch.setattr(nodes, "plan_from_text", rec_plan_from_text)
    monkeypatch.setattr(nodes, "refine_plan", rec_refine_plan)
    monkeypatch.setattr(nodes, "propose_edit", rec_propose_edit)


def _write_fixture(case_id: str, captured: dict[str, Any]) -> None:
    RESPONSES_DIR.mkdir(exist_ok=True)
    payload = {
        "case": case_id,
        # Noted so a replay suite passing against a model you no longer run is visible
        # (EVAL-PLAN.md §8, "recorded responses drift from reality").
        "model": os.environ.get("LLM_MODEL", "unknown"),
        "recorded_at": _dt.date.today().isoformat(),
        "calls": captured,
    }
    (RESPONSES_DIR / f"{case_id}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )


# --- driving the graph ---------------------------------------------------------------


def _base_state(**over: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "user_message": "",
        "payload": None,
        "canvas_context": CanvasContext(),
        "vision_enabled": False,  # see module docstring
        "spec_enabled": True,
        "input_kind": "text",
        "base_plan": None,
        "layout_params": {"gap_scale": 1.0},
        "iterations": 0,
        "cost_usd": 0.0,
    }
    state.update(over)
    return state


async def _drive(state: dict[str, Any]) -> tuple[list[dict], dict[str, float], float]:
    """Walk the real graph, collecting what `record_from_run` needs (mirrors main.py and
    tests/eval/harness.py): every critic visit, per-node time summed across repeats."""
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


def run_tier2_case(
    case: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    *,
    record: bool,
    meter: Any = None,
) -> tuple[dict[str, Any], RunRecord]:
    captured: dict[str, Any] = {}
    if record:
        _install_record(case, monkeypatch, captured)
    else:
        _install_replay(case, monkeypatch)

    inp = case["input"]
    if case["kind"] == "create":
        state = _base_state(payload=inp["request"])
    else:
        state = _base_state(payload=inp["follow_up"], base_plan=DiagramPlan(**inp["base_plan"]))
    if meter is not None:
        state["meter"] = meter

    passes, stage_ms, total_ms = asyncio.run(_drive(state))
    rec = record_from_run(
        state,
        outcome="completed",
        passes=passes,
        stage_ms=stage_ms,
        total_ms=total_ms,
        meter=meter,
        shapes=len(state.get("actions") or []),
    )
    if record and captured:
        _write_fixture(case["id"], captured)
    return state, rec


# --- checking the result -----------------------------------------------------------


def check_tier2_properties(case: dict[str, Any], state: dict[str, Any]) -> list[str]:
    """Every claim the case makes about the diagram, checked against what the run produced.
    Semantic checks read `llm_plan` (the model picks node ids, but labels are predictable);
    geometry mirrors `tests/eval/harness.py`. Returns violation strings; empty means pass.
    """
    exp = case.get("expect", {})
    report = state.get("plan_report") or {}
    problems: list[str] = []

    got_intent = report.get("intent") or ("answer" if state.get("answered") else "create")
    if (want := exp.get("intent")) is not None and got_intent != want:
        problems.append(f"intent: expected {want!r}, got {got_intent!r}")

    if case["kind"] == "question":
        if not state.get("answered"):
            problems.append("question case did not answer (nothing in state['answered'])")
        reply = (state.get("reply") or "").lower()
        for frag in exp.get("reply_contains", []):
            if frag.lower() not in reply:
                problems.append(f"reply did not mention {frag!r}: {reply!r}")
        return problems

    plan = state.get("llm_plan")
    if not isinstance(plan, DiagramPlan) or not plan.nodes:
        problems.append("no plan with nodes was produced")
        return problems

    hay = " | ".join(f"{n.label} {n.subtitle or ''} {n.kind or ''}" for n in plan.nodes).lower()
    for term in exp.get("must_contain", []):
        if term.lower() not in hay:
            problems.append(f"missing required concept {term!r}")
    for term in exp.get("must_not_contain", []):
        if term.lower() in hay:
            problems.append(f"hallucinated forbidden concept {term!r}")

    for pair in exp.get("must_connect", []):
        a, b = pair
        ids_a = [n.id for n in plan.nodes if a.lower() in n.label.lower()]
        ids_b = [n.id for n in plan.nodes if b.lower() in n.label.lower()]
        linked = any(
            (e.source in ids_a and e.target in ids_b) or (e.source in ids_b and e.target in ids_a)
            for e in plan.edges
        )
        if not linked:
            problems.append(f"missing connection {a!r} <-> {b!r}")

    n_nodes, n_edges = len(plan.nodes), len(plan.edges)
    if (lo := exp.get("nodes_min")) is not None and n_nodes < lo:
        problems.append(f"expected >= {lo} nodes, got {n_nodes}")
    if (hi := exp.get("nodes_max")) is not None and n_nodes > hi:
        problems.append(f"expected <= {hi} nodes, got {n_nodes}")
    if (lo := exp.get("edges_min")) is not None and n_edges < lo:
        problems.append(f"expected >= {lo} edges, got {n_edges}")
    if (hi := exp.get("edges_max")) is not None and n_edges > hi:
        problems.append(f"expected <= {hi} edges, got {n_edges}")

    if exp.get("expect_assumptions"):
        spec = state.get("spec")
        if len(getattr(spec, "assumptions", []) or []) == 0:
            problems.append("a vague prompt should declare assumptions; the spec declared none")

    final_critique = state.get("critique") or {}
    geo_kinds = {i.get("kind") for i in final_critique.get("issues", [])}
    if exp.get("clean", False):
        if final_critique.get("needs_refine"):
            problems.append("final critic pass still wants a refine")
        if hit := geo_kinds & _BLOCKING_GEOMETRY:
            problems.append(f"geometry issues remain after refine: {sorted(hit)}")

    blocking = sum(1 for i in report.get("issues", []) if i.get("severity") == "error")
    budget = exp.get("blocking_issues_max", 0)
    if blocking > budget:
        problems.append(f"{blocking} blocking validator issue(s), budget was {budget}")

    refines = max(0, int(state.get("iterations", 0) or 0) - 1)
    if (hi := exp.get("max_refines")) is not None and refines > hi:
        problems.append(f"needed {refines} refine pass(es), budget was {hi}")

    if (want := exp.get("summary_contains")) is not None:
        if want.lower() not in (report.get("summary") or "").lower():
            problems.append(f"edit summary did not mention {want!r}: {report.get('summary')!r}")

    return problems
