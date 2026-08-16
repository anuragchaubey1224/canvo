"""Integration test: the graph turns an OpenAPI spec into an API-surface diagram."""
from __future__ import annotations

import asyncio
import json

from app.graph.build import graph
from app.schema import CanvasContext

SPEC = json.dumps(
    {
        "openapi": "3.0.0",
        "info": {"title": "Shop API"},
        "paths": {
            "/users": {"get": {"tags": ["users"]}},
            "/orders": {"post": {"tags": ["orders"]}},
        },
    }
)


def test_openapi_input_produces_api_surface():
    res = asyncio.run(
        graph.ainvoke(
            {"payload": SPEC, "canvas_context": CanvasContext(), "iterations": 0, "cost_usd": 0.0}
        )
    )
    assert res["input_kind"] == "openapi"

    actions = res["actions"]
    boxes = {a.shape.id for a in actions if a.shape and a.shape.type == "geo"}
    arrows = [a for a in actions if a.shape and a.shape.type == "arrow"]

    assert "api-root" in boxes
    assert {"grp-users", "grp-orders"} <= boxes
    assert any(a.shape.from_id == "api-root" and a.shape.to_id == "grp-users" for a in arrows)
