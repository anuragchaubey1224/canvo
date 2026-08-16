"""Deterministic ERD layout: a parsed SQL schema → canvas actions.

Kept deterministic on purpose — no LLM here. It gives us a correct, reproducible
baseline (useful as an eval reference) before the LLM-driven layout lands for fuzzy
inputs like plain-text descriptions.
"""
from __future__ import annotations

import re

from app.schema import AgentAction, Shape
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
