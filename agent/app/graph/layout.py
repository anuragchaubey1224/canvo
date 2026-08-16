"""Deterministic ERD layout: a parsed SQL schema → canvas actions.

Kept deterministic on purpose — no LLM here. It gives us a correct, reproducible
baseline (useful as an eval reference) before the LLM-driven layout lands for fuzzy
inputs like plain-text descriptions.
"""

from __future__ import annotations

import re

from app.graph.planner_llm import DiagramPlan
from app.schema import AgentAction, Shape
from app.tools.parse_openapi import ParsedAPI
from app.tools.parse_sql import ParsedSchema, Table

_BOX_W = 240
_GAP_X = 440  # generous so tables (which grow to fit text) don't crowd their arrows
_GAP_Y = 420
_X0 = 80
_Y0 = 80


def _slug(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "-", name).strip("-").lower() or "x"


def _tid(name: str) -> str:
    return f"tbl-{_slug(name)}"


def _table_text(table: Table) -> str:
    lines = [table.name]
    for col in table.columns:
        marks = []
        if col.is_primary_key:
            marks.append("PK")
        if col.is_foreign_key:
            marks.append("FK")
        suffix = f" [{','.join(marks)}]" if marks else ""
        typ = f" {col.type}" if col.type else ""
        lines.append(f"- {col.name}{typ}{suffix}")
    return "\n".join(lines)


def build_erd_actions(schema: ParsedSchema, *, cols: int = 3) -> list[AgentAction]:
    """One geo box per table (grid layout) + one bound arrow per relation."""
    actions: list[AgentAction] = []
    pos: dict[str, tuple[float, float]] = {}

    for i, table in enumerate(schema.tables):
        row, col = divmod(i, max(1, cols))
        x = _X0 + col * _GAP_X
        y = _Y0 + row * _GAP_Y
        pos[table.name] = (x, y)
        height = max(80, 44 + 20 * len(table.columns))
        actions.append(
            AgentAction(
                type="create",
                shape=Shape(
                    id=_tid(table.name),
                    type="geo",
                    x=x,
                    y=y,
                    w=_BOX_W,
                    h=height,
                    text=_table_text(table),
                ),
            )
        )

    for rel in schema.relations:
        fx, fy = pos.get(rel.from_table, (_X0, _Y0))
        actions.append(
            AgentAction(
                type="create",
                shape=Shape(
                    id=f"rel-{_slug(rel.from_table)}-{_slug(rel.from_column)}-{_slug(rel.to_table)}",
                    type="arrow",
                    x=fx + _BOX_W,
                    y=fy + 20,
                    from_id=_tid(rel.from_table),
                    to_id=_tid(rel.to_table),
                    text=f"{rel.from_column} → {rel.to_column}",
                ),
            )
        )

    return actions


def build_api_actions(api: ParsedAPI, *, cols: int = 3) -> list[AgentAction]:
    """A root API node + one box per group listing its endpoints, arrows root→group."""
    actions: list[AgentAction] = []
    root_id = "api-root"

    actions.append(
        AgentAction(
            type="create",
            shape=Shape(
                id=root_id,
                type="geo",
                x=_X0,
                y=_Y0,
                w=_BOX_W,
                h=80,
                text=f"API: {api.title}\n{api.endpoint_count} endpoints · {len(api.groups)} groups",
            ),
        )
    )

    y_groups = _Y0 + _GAP_Y
    for i, group in enumerate(api.groups):
        row, col = divmod(i, max(1, cols))
        x = _X0 + col * _GAP_X
        y = y_groups + row * _GAP_Y
        lines = [group.name] + [f"{e.method} {e.path}" for e in group.endpoints]
        height = max(80, 44 + 20 * len(group.endpoints))
        gid = f"grp-{_slug(group.name)}"
        actions.append(
            AgentAction(
                type="create",
                shape=Shape(
                    id=gid, type="geo", x=x, y=y, w=_BOX_W, h=height, text="\n".join(lines)
                ),
            )
        )
        actions.append(
            AgentAction(
                type="create",
                shape=Shape(
                    id=f"edge-{_slug(group.name)}",
                    type="arrow",
                    x=x,
                    y=y,
                    from_id=root_id,
                    to_id=gid,
                ),
            )
        )

    return actions


def build_graph_actions(plan: DiagramPlan, *, cols: int = 3) -> list[AgentAction]:
    """Generic node/edge diagram (from the LLM planner): boxes in a grid + bound arrows."""
    actions: list[AgentAction] = []

    for i, node in enumerate(plan.nodes):
        row, col = divmod(i, max(1, cols))
        actions.append(
            AgentAction(
                type="create",
                shape=Shape(
                    id=f"n-{_slug(node.id)}",
                    type="geo",
                    x=_X0 + col * _GAP_X,
                    y=_Y0 + row * _GAP_Y,
                    w=_BOX_W,
                    h=80,
                    text=node.label,
                ),
            )
        )

    for i, edge in enumerate(plan.edges):
        actions.append(
            AgentAction(
                type="create",
                shape=Shape(
                    id=f"e-{i}-{_slug(edge.source)}-{_slug(edge.target)}",
                    type="arrow",
                    x=_X0,
                    y=_Y0,
                    from_id=f"n-{_slug(edge.source)}",
                    to_id=f"n-{_slug(edge.target)}",
                    text=edge.label or "",
                ),
            )
        )

    return actions
