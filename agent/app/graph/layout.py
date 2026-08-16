"""Deterministic layout: parsed inputs / LLM plans → canvas actions.

Kept deterministic on purpose — no LLM here. The LLM (planner) decides *what* the diagram
contains; this module decides *where* everything goes, so geometry is reproducible and the
Critic's refine loop has a reliable lever (`gap_scale`).

Freeform plans get a layered top-down layout (Sugiyama-lite): nodes are ranked by
dependency depth, each rank becomes a row, rows are centered, and a single barycenter
pass reduces edge crossings. Groups become colored container panels sized to fit their
members (Eraser-style swimlanes).
"""

from __future__ import annotations

import re

from app.graph.planner_llm import DiagramPlan, PlanEdge, PlanNode
from app.schema import AgentAction, Shape
from app.tools.parse_openapi import ParsedAPI
from app.tools.parse_sql import ParsedSchema, Table

_BOX_W = 240
_GAP_X = 440  # generous so tables (which grow to fit text) don't crowd their arrows
_GAP_Y = 420
_X0 = 80
_Y0 = 80

# Flow-node geometry (layered layout). Calibrated against Eraser's density: compact
# cards and tight gaps mechanically shorten every arrow — most "routing quality" is
# actually layout density, so resist the urge to widen these for breathing room.
_NODE_W = 200
_NODE_H = 64
_DECISION_H = 96  # diamonds need more vertical room for their label
_FLOW_GAP_X = 56  # between siblings in a row (top-down flows)
_FLOW_GAP_Y = 72  # between rows/ranks (top-down flows)
_FLOW_GAP_RX = 64  # between rank-columns (left-to-right flows inside panels)
_FLOW_GAP_RY = 40  # between stacked siblings (left-to-right flows)

# Panels wrap into a grid once a row of them would exceed this width (pre-scale), so a
# chain of stages packs like Eraser's 2-column look instead of one tall column.
_ROW_CAP = 1700.0

# Container (group panel) chrome — tight, Eraser-style panels that hug their content.
_GROUP_PAD = 28
_GROUP_TITLE_H = 40
_GROUP_GAP_X = 90
_GROUP_GAP_Y = 110

# Default node color by semantic kind (tldraw color tokens). Open set: unknown kinds
# simply get no color and render as plain boxes (ADR-013).
_KIND_COLOR = {
    "service": "blue",
    "datastore": "violet",
    "decision": "orange",
    "client": "light-blue",
    "external": "grey",
    "queue": "yellow",
    "start": "green",
    "end": "green",
    "note": "grey",
}

# Container accents cycle through these when the planner doesn't pick one.
_GROUP_COLORS = ("blue", "violet", "orange", "green", "light-blue", "yellow")


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


def build_erd_actions(
    schema: ParsedSchema, *, cols: int = 3, gap_scale: float = 1.0
) -> list[AgentAction]:
    """One geo box per table (grid layout) + one bound arrow per relation.

    `gap_scale` widens the grid pitch; the Critic bumps it to resolve crowding (refine loop).
    """
    actions: list[AgentAction] = []
    pos: dict[str, tuple[float, float]] = {}
    gap_x = _GAP_X * gap_scale
    gap_y = _GAP_Y * gap_scale

    for i, table in enumerate(schema.tables):
        row, col = divmod(i, max(1, cols))
        x = _X0 + col * gap_x
        y = _Y0 + row * gap_y
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
                    color="violet",
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


def build_api_actions(
    api: ParsedAPI, *, cols: int = 3, gap_scale: float = 1.0
) -> list[AgentAction]:
    """A root API node + one box per group listing its endpoints, arrows root→group."""
    actions: list[AgentAction] = []
    root_id = "api-root"
    gap_x = _GAP_X * gap_scale
    gap_y = _GAP_Y * gap_scale

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
                color="blue",
            ),
        )
    )

    y_groups = _Y0 + gap_y
    for i, group in enumerate(api.groups):
        row, col = divmod(i, max(1, cols))
        x = _X0 + col * gap_x
        y = y_groups + row * gap_y
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


# --------------------------------------------------------------------------------------
# Layered flow layout (freeform plans)
# --------------------------------------------------------------------------------------


def _node_size(kind: str | None) -> tuple[float, float]:
    if kind == "decision":
        return (_NODE_W, _DECISION_H)
    return (_NODE_W, _NODE_H)


def _ranks(ids: list[str], edges: list[tuple[str, str]]) -> dict[str, int]:
    """Longest-path layering over a (mostly) DAG; cycle members degrade gracefully."""
    id_set = set(ids)
    preds: dict[str, list[str]] = {i: [] for i in ids}
    succs: dict[str, list[str]] = {i: [] for i in ids}
    indeg: dict[str, int] = {i: 0 for i in ids}
    for s, t in edges:
        if s in id_set and t in id_set and s != t:
            succs[s].append(t)
            preds[t].append(s)
            indeg[t] += 1

    ranks: dict[str, int] = {}
    queue = [i for i in ids if indeg[i] == 0]
    for i in queue:
        ranks[i] = 0
    remaining = dict(indeg)
    done: set[str] = set()
    while queue:
        n = queue.pop(0)
        if n in done:
            continue
        done.add(n)
        for m in succs[n]:
            ranks[m] = max(ranks.get(m, 0), ranks[n] + 1)
            remaining[m] -= 1
            if remaining[m] == 0:
                queue.append(m)

    # Cycles / stranded nodes: rank just below any already-ranked predecessor, input order.
    for i in ids:
        if i not in ranks:
            ranked = [ranks[p] for p in preds[i] if p in ranks]
            ranks[i] = (max(ranked) + 1) if ranked else 0
    return ranks


def _barycenter(
    nid: str, preds: dict[str, list[str]], prev_index: dict[str, int], fallback: float
) -> float:
    ps = [prev_index[p] for p in preds[nid] if p in prev_index]
    return sum(ps) / len(ps) if ps else fallback


def _layout_flow(
    nodes: list[PlanNode],
    edges: list[PlanEdge],
    gap_scale: float,
    direction: str = "down",
) -> tuple[dict[str, tuple[float, float]], float, float]:
    """Layered flow layout. Returns (positions relative to (0,0), width, height).

    `direction="down"` stacks ranks as rows (whole-canvas flows); `direction="right"`
    stacks them as columns — used inside group panels so they come out wide and short,
    the way Eraser draws stage lanes.
    """
    if not nodes:
        return {}, 0.0, 0.0

    ids = [n.id for n in nodes]
    kind_of = {n.id: n.kind for n in nodes}
    ranks = _ranks(ids, [(e.source, e.target) for e in edges])
    lanes: dict[int, list[str]] = {}
    for i in ids:
        lanes.setdefault(ranks[i], []).append(i)

    preds: dict[str, list[str]] = {i: [] for i in ids}
    for e in edges:
        if e.source in preds and e.target in preds:
            preds[e.target].append(e.source)

    # One barycenter pass: order each lane by the mean index of its predecessors in the
    # lane before — cheap, and removes most crossings for the small graphs we draw.
    prev_index: dict[str, int] = {}
    for r in sorted(lanes):
        lane = lanes[r]
        if prev_index:
            fallback = float(len(lane))
            weight = {nid: _barycenter(nid, preds, prev_index, fallback) for nid in lane}
            lane.sort(key=weight.__getitem__)
        prev_index = {nid: idx for idx, nid in enumerate(lane)}

    pos: dict[str, tuple[float, float]] = {}
    if direction == "down":
        gap_x = _FLOW_GAP_X * gap_scale
        gap_y = _FLOW_GAP_Y * gap_scale
        lane_width = {
            r: sum(_node_size(kind_of[n])[0] for n in lane) + gap_x * (len(lane) - 1)
            for r, lane in lanes.items()
        }
        total_w = max(lane_width.values())
        y = 0.0
        for r in sorted(lanes):
            lane = lanes[r]
            row_h = max(_node_size(kind_of[n])[1] for n in lane)
            x = (total_w - lane_width[r]) / 2  # center each row on the widest one
            for nid in lane:
                w, h = _node_size(kind_of[nid])
                pos[nid] = (x, y + (row_h - h) / 2)
                x += w + gap_x
            y += row_h + gap_y
        return pos, total_w, y - gap_y

    # direction == "right": ranks become columns, siblings stack vertically.
    gap_cx = _FLOW_GAP_RX * gap_scale
    gap_cy = _FLOW_GAP_RY * gap_scale
    lane_height = {
        r: sum(_node_size(kind_of[n])[1] for n in lane) + gap_cy * (len(lane) - 1)
        for r, lane in lanes.items()
    }
    total_h = max(lane_height.values())
    x = 0.0
    for r in sorted(lanes):
        lane = lanes[r]
        col_w = max(_node_size(kind_of[n])[0] for n in lane)
        y = (total_h - lane_height[r]) / 2  # center each column on the tallest one
        for nid in lane:
            w, h = _node_size(kind_of[nid])
            pos[nid] = (x + (col_w - w) / 2, y)
            y += h + gap_cy
        x += col_w + gap_cx
    return pos, x - gap_cx, total_h


def _node_shape(
    node: PlanNode, x: float, y: float, parent_id: str | None, accent: str | None = None
) -> Shape:
    w, h = _node_size(node.kind)
    return Shape(
        id=f"n-{_slug(node.id)}",
        type="geo",
        x=x,
        y=y,
        w=w,
        h=h,
        text=node.label,
        kind=node.kind,
        subtitle=node.subtitle,
        color=accent or _KIND_COLOR.get(node.kind or ""),
        parent_id=parent_id,
        icon=node.icon,
    )


def _edge_actions(
    edges: list[PlanEdge], known: set[str], accent_of: dict[str, str] | None = None
) -> list[AgentAction]:
    """Arrows between nodes, tinted with the SOURCE node's accent (Eraser-style flows)."""
    actions = []
    for i, edge in enumerate(edges):
        if edge.source not in known or edge.target not in known:
            continue  # planner slip — dropping beats a dangling arrow
        label = (edge.label or "").strip()
        if len(label) > 18:  # long labels wrap into a mess on short arrows — hard cap
            label = label[:18].rsplit(" ", 1)[0] if " " in label[:18] else label[:18]
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
                    text=label,
                    color=(accent_of or {}).get(edge.source),
                ),
            )
        )
    return actions


def _title_action(title: str | None) -> list[AgentAction]:
    if not title or not title.strip():
        return []
    return [
        AgentAction(
            type="create",
            shape=Shape(
                id="diagram-title",
                type="text",
                x=_X0,
                y=_Y0 - 96,
                w=640,
                h=44,
                text=title.strip(),
            ),
        )
    ]


def build_graph_actions(
    plan: DiagramPlan, *, cols: int = 3, gap_scale: float = 1.0
) -> list[AgentAction]:
    """Freeform plan → layered layout. With groups: one container panel per group
    (sized to fit its members), panels arranged by their own dependency rank; without
    groups: a single top-down layered flow. Emit order = containers, nodes, arrows —
    creation order is z-order on the canvas."""
    node_ids = {n.id for n in plan.nodes}

    if not plan.groups:
        pos, _w, _h = _layout_flow(plan.nodes, plan.edges, gap_scale)
        accent_of = {n.id: _KIND_COLOR.get(n.kind or "", "grey") for n in plan.nodes}
        actions = [
            AgentAction(
                type="create",
                shape=_node_shape(n, _X0 + pos[n.id][0], _Y0 + pos[n.id][1], None),
            )
            for n in plan.nodes
        ]
        return _title_action(plan.title) + actions + _edge_actions(plan.edges, node_ids, accent_of)

    # ---- grouped layout ----
    group_ids = [g.id for g in plan.groups]
    group_of = {n.id: (n.group if n.group in set(group_ids) else None) for n in plan.nodes}
    # Each ungrouped node gets its OWN slot, so a loose "Start" ranks above the panels it
    # feeds and a loose "End" below the ones feeding it — bunching them into one shared
    # pseudo-group drags them all to the same row and stretches arrows across the canvas.
    loose_slot = {n.id: f"__loose__{n.id}" for n in plan.nodes if group_of[n.id] is None}
    slot_of = {n.id: (group_of[n.id] or loose_slot[n.id]) for n in plan.nodes}
    slots = list(group_ids) + list(loose_slot.values())

    # Rank the panels themselves by cross-slot edges, so stages read in flow order.
    cross: list[tuple[str, str]] = []
    for e in plan.edges:
        if e.source in slot_of and e.target in slot_of:
            if slot_of[e.source] != slot_of[e.target]:
                cross.append((slot_of[e.source], slot_of[e.target]))
    granks = _ranks(slots, cross)

    # Lay out each slot's members locally (left-to-right, so panels come out wide and
    # short like Eraser's stage lanes), then size its panel around them.
    members: dict[str, list[PlanNode]] = {gid: [] for gid in slots}
    for n in plan.nodes:
        members[slot_of[n.id]].append(n)
    local: dict[str, tuple[dict[str, tuple[float, float]], float, float]] = {}
    for gid in slots:
        ids_in = {n.id for n in members[gid]}
        inner = [e for e in plan.edges if e.source in ids_in and e.target in ids_in]
        local[gid] = _layout_flow(members[gid], inner, gap_scale, direction="right")

    def panel_size(gid: str) -> tuple[float, float]:
        _pos, w, h = local[gid]
        if gid.startswith("__loose__"):
            return (w, h)
        return (w + 2 * _GROUP_PAD, h + _GROUP_PAD + _GROUP_TITLE_H)

    # Pack panels into a grid in flow order (rank, then declaration order), wrapping
    # rows at a width cap — a linear 1→2→3→4 stage chain becomes a compact 2-column
    # grid instead of one tall column.
    slot_index = {gid: i for i, gid in enumerate(slots)}
    ordered = sorted(slots, key=lambda gid: (granks[gid], slot_index[gid]))
    ggap_x = _GROUP_GAP_X * gap_scale
    ggap_y = _GROUP_GAP_Y * gap_scale
    cap = _ROW_CAP * gap_scale
    packed: list[list[str]] = []
    current: list[str] = []
    current_w = 0.0
    for gid in ordered:
        pw = panel_size(gid)[0]
        next_w = pw if not current else current_w + ggap_x + pw
        if current and next_w > cap:
            packed.append(current)
            current, next_w = [], pw
        current, current_w = current + [gid], next_w
    if current:
        packed.append(current)

    row_w = {
        r: sum(panel_size(g)[0] for g in row) + ggap_x * (len(row) - 1)
        for r, row in enumerate(packed)
    }
    total_w = max(row_w.values())

    containers: list[AgentAction] = []
    node_actions: list[AgentAction] = []
    labels = {g.id: g.label for g in plan.groups}
    colors = {
        g.id: (g.color or _GROUP_COLORS[i % len(_GROUP_COLORS)]) for i, g in enumerate(plan.groups)
    }

    y = float(_Y0)
    for r, row in enumerate(packed):
        row_h = max(panel_size(g)[1] for g in row)
        x = _X0 + (total_w - row_w[r]) / 2
        for gid in row:
            pw, ph = panel_size(gid)
            pos, _w, _h = local[gid]
            if gid.startswith("__loose__"):
                origin = (x, y + (row_h - ph) / 2)  # center a lone node on its panel row
                parent = None
            else:
                cid = f"g-{_slug(gid)}"
                containers.append(
                    AgentAction(
                        type="create",
                        shape=Shape(
                            id=cid,
                            type="container",
                            x=x,
                            y=y,
                            w=pw,
                            h=ph,
                            text=labels[gid],
                            color=colors[gid],
                        ),
                    )
                )
                origin = (x + _GROUP_PAD, y + _GROUP_TITLE_H)
                parent = cid
            g_accent = colors.get(gid)
            for n in members[gid]:
                nx, ny = pos[n.id]
                node_actions.append(
                    AgentAction(
                        type="create",
                        shape=_node_shape(n, origin[0] + nx, origin[1] + ny, parent, g_accent),
                    )
                )
            x += pw + ggap_x
        y += row_h + ggap_y

    # Arrows carry their source node's group accent (loose nodes: kind color).
    accent_of = {
        n.id: colors.get(slot_of[n.id]) or _KIND_COLOR.get(n.kind or "", "grey") for n in plan.nodes
    }
    return (
        _title_action(plan.title)
        + containers
        + node_actions
        + _edge_actions(plan.edges, node_ids, accent_of)
    )
