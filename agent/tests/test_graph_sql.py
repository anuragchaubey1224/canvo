"""Integration test: the graph turns a SQL schema into ERD canvas actions."""

from __future__ import annotations

import asyncio

from app.graph.build import graph
from app.schema import CanvasContext

DDL = """
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL
);
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id)
);
"""


def _run(state):
    return asyncio.run(graph.ainvoke(state))


def test_sql_input_produces_erd():
    res = _run(
        {
            "user_message": DDL,
            "canvas_context": CanvasContext(),
            "iterations": 0,
            "cost_usd": 0.0,
        }
    )
    assert res["input_kind"] == "sql"

    actions = res["actions"]
    boxes = {a.shape.id for a in actions if a.shape and a.shape.type == "geo"}
    arrows = [a for a in actions if a.shape and a.shape.type == "arrow"]

    assert {"tbl-users", "tbl-orders"} <= boxes
    assert any(a.shape.from_id == "tbl-orders" and a.shape.to_id == "tbl-users" for a in arrows)


def test_text_input_falls_back_to_stub():
    res = _run(
        {
            "user_message": "draw a login flow",
            "canvas_context": CanvasContext(),
            "iterations": 0,
            "cost_usd": 0.0,
        }
    )
    assert res["input_kind"] == "text"
    assert len(res["actions"]) == 3
