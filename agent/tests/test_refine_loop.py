"""The Critic's bounded refine loop actually self-corrects a crowded layout.

Runs fully offline: the SQL path is deterministic and we disable the vision pass, so
the whole graph executes with no network. A wide schema overlaps at the base spacing;
the Critic must widen `gap_scale` and converge to a clean layout within the cap.
"""

from __future__ import annotations

import asyncio

from app.graph.build import graph
from app.graph.critique import analyze_geometry
from app.graph.layout import build_erd_actions
from app.tools.parse_sql import parse_sql


def _wide_sql(n_tables: int = 4, n_cols: int = 20) -> str:
    stmts = []
    for t in range(n_tables):
        cols = ["id INT PRIMARY KEY"] + [f"col_{i} VARCHAR(20)" for i in range(n_cols)]
        stmts.append(f"CREATE TABLE t_{t} (" + ", ".join(cols) + ");")
    return "\n".join(stmts)


def test_wide_schema_overlaps_at_base_scale_and_clears_when_widened():
    schema = parse_sql(_wide_sql())
    assert analyze_geometry(build_erd_actions(schema, gap_scale=1.0)).has_overlap
    assert not analyze_geometry(build_erd_actions(schema, gap_scale=1.5)).has_overlap


def test_refine_loop_resolves_overlap():
    state = {
        "payload": _wide_sql(),
        "input_kind": "sql",
        "user_message": "",
        "vision_enabled": False,  # keep the run fully offline
        "layout_params": {"gap_scale": 1.0},
        "iterations": 0,
        "cost_usd": 0.0,
    }
    result = asyncio.run(graph.ainvoke(state))

    # It should have needed at least one refine pass (2+ critic visits), and settled.
    assert 2 <= result["iterations"] <= 3
    assert not analyze_geometry(result["actions"]).has_overlap
    assert (result.get("layout_params") or {}).get("gap_scale", 1.0) > 1.0
    assert result["critique"]["needs_refine"] is False


def test_clean_input_needs_no_refine():
    state = {
        "payload": "CREATE TABLE users (id INT PRIMARY KEY, email VARCHAR(255));",
        "input_kind": "sql",
        "user_message": "",
        "vision_enabled": False,
        "layout_params": {"gap_scale": 1.0},
        "iterations": 0,
        "cost_usd": 0.0,
    }
    result = asyncio.run(graph.ainvoke(state))
    assert result["iterations"] == 1  # one critic visit, no loop
    assert result["critique"]["needs_refine"] is False
