"""Orthogonal arrow router with obstacle avoidance — Canvo's own routing engine (P2).

tldraw's elbow arrows only avoid the two shapes they bind; every other card and panel
is invisible to them, so cross-panel arrows cut straight through content. This module
routes each arrow as an axis-aligned polyline over a sparse coordinate grid using A*:

  - **Obstacles**: every node card (inflated by a clearance margin) and every panel the
    arrow does not start or end in. Own panels are pass-through.
  - **Grid**: candidate x/y coordinates from obstacle edges ± clearance — the classic
    sparse "interesting coordinates" formulation, so the search space stays tiny.
  - **Cost**: Manhattan length + a turn penalty (fewer bends read cleaner) + a shared-
    corridor penalty (arrows spread out instead of stacking on one line).

The routed waypoints ride on the arrow's `points` (flat [x0,y0,x1,y1,...]) with a label
anchor on the longest segment. Arrows the router can't solve keep `points=None` and fall
back to the client's bound elbow arrows.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from app.schema import AgentAction, Shape

_CLEAR = 16.0  # min clearance between a route and a card
_PANEL_CLEAR = 6.0  # routes may hug panels closer than cards
_TURN_COST = 60.0  # per bend — prefer straighter routes
_SHARED_COST = 48.0  # per reused grid edge — spread parallel arrows apart
_MARGIN = 48.0  # routable border around the whole diagram


@dataclass(frozen=True)
class _Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    def blocks(self, ax: float, ay: float, bx: float, by: float) -> bool:
        """Does the axis-aligned segment a→b pass through this rect's interior?"""
        lo_x, hi_x = min(ax, bx), max(ax, bx)
        lo_y, hi_y = min(ay, by), max(ay, by)
        return lo_x < self.x1 and hi_x > self.x0 and lo_y < self.y1 and hi_y > self.y0


def _inflate(s: Shape, pad: float) -> _Rect:
    return _Rect(s.x - pad, s.y - pad, s.x + s.w + pad, s.y + s.h + pad)


def _anchor(src: Shape, dst: Shape) -> tuple[float, float, float, float]:
    """Facing-edge exit point + its projection one clearance step outside the shape."""
    scx, scy = src.x + src.w / 2, src.y + src.h / 2
    dcx, dcy = dst.x + dst.w / 2, dst.y + dst.h / 2
    dx, dy = dcx - scx, dcy - scy
    if abs(dx) >= abs(dy):
        x = src.x + src.w if dx >= 0 else src.x
        out = x + _CLEAR if dx >= 0 else x - _CLEAR
        return (x, scy, out, scy)
    y = src.y + src.h if dy >= 0 else src.y
    out = y + _CLEAR if dy >= 0 else y - _CLEAR
    return (scx, y, scx, out)


def _simplify(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Drop collinear intermediate points."""
    if len(points) <= 2:
        return points
    out = [points[0]]
    for i in range(1, len(points) - 1):
        (ax, ay), (bx, by), (cx, cy) = out[-1], points[i], points[i + 1]
        if (ax == bx == cx) or (ay == by == cy):
            continue
        out.append(points[i])
    out.append(points[-1])
    return out


def _astar(
    xs: list[float],
    ys: list[float],
    start: tuple[int, int],
    goal: tuple[int, int],
    blocked,
    used: set[tuple[tuple[int, int], tuple[int, int]]],
) -> list[tuple[int, int]] | None:
    """A* over the sparse grid; state = (ix, iy, incoming direction)."""

    def h(ix: int, iy: int) -> float:
        return abs(xs[ix] - xs[goal[0]]) + abs(ys[iy] - ys[goal[1]])

    # dir: 0=+x 1=-x 2=+y 3=-y, -1=start
    open_q: list[tuple[float, float, int, int, int]] = [(h(*start), 0.0, start[0], start[1], -1)]
    best: dict[tuple[int, int, int], float] = {(start[0], start[1], -1): 0.0}
    parent: dict[tuple[int, int, int], tuple[int, int, int]] = {}

    while open_q:
        _f, g, ix, iy, d = heapq.heappop(open_q)
        if best.get((ix, iy, d), float("inf")) < g:
            continue
        if (ix, iy) == goal:
            path = [(ix, iy)]
            key = (ix, iy, d)
            while key in parent:
                key = parent[key]
                path.append((key[0], key[1]))
            path.reverse()
            return path
        for nd, (sx, sy) in enumerate(((1, 0), (-1, 0), (0, 1), (0, -1))):
            nx, ny = ix + sx, iy + sy
            if not (0 <= nx < len(xs) and 0 <= ny < len(ys)):
                continue
            if blocked(ix, iy, nx, ny):
                continue
            step = abs(xs[nx] - xs[ix]) + abs(ys[ny] - ys[iy])
            cost = g + step
            if d != -1 and nd != d:
                cost += _TURN_COST
            edge = ((min(ix, nx), min(iy, ny)), (max(ix, nx), max(iy, ny)))
            if edge in used:
                cost += _SHARED_COST
            key = (nx, ny, nd)
            if cost < best.get(key, float("inf")):
                best[key] = cost
                parent[key] = (ix, iy, d)
                heapq.heappush(open_q, (cost + h(nx, ny), cost, nx, ny, nd))
    return None


def route_arrows(actions: list[AgentAction]) -> list[AgentAction]:
    """Attach obstacle-avoiding orthogonal waypoints to every box-to-box arrow."""
    boxes: dict[str, Shape] = {}
    containers: dict[str, Shape] = {}
    arrows: list[Shape] = []
    for a in actions:
        s = a.shape
        if a.type != "create" or not s:
            continue
        if s.type == "geo":
            boxes[s.id] = s
        elif s.type == "container":
            containers[s.id] = s
        elif s.type == "arrow":
            arrows.append(s)

    if not arrows or not boxes:
        return actions

    # Sparse global grid: obstacle edges ± clearance, plus shape center lines for exits.
    xs_set: set[float] = set()
    ys_set: set[float] = set()
    shapes = list(boxes.values()) + list(containers.values())
    for s in shapes:
        xs_set.update((s.x - _CLEAR, s.x + s.w + _CLEAR, s.x + s.w / 2))
        ys_set.update((s.y - _CLEAR, s.y + s.h + _CLEAR, s.y + s.h / 2))
    min_x = min(s.x for s in shapes) - _MARGIN
    max_x = max(s.x + s.w for s in shapes) + _MARGIN
    min_y = min(s.y for s in shapes) - _MARGIN
    max_y = max(s.y + s.h for s in shapes) + _MARGIN
    xs_set.update((min_x, max_x))
    ys_set.update((min_y, max_y))

    used: set[tuple[tuple[int, int], tuple[int, int]]] = set()

    for arrow in arrows:
        src = boxes.get(arrow.from_id or "")
        dst = boxes.get(arrow.to_id or "")
        if not src or not dst:
            continue

        sx, sy, sox, soy = _anchor(src, dst)
        tx_, ty_, tox, toy = _anchor(dst, src)

        xs = sorted(xs_set | {sox, tox})
        ys = sorted(ys_set | {soy, toy})
        xi = {v: i for i, v in enumerate(xs)}
        yi = {v: i for i, v in enumerate(ys)}

        own_parents = {src.parent_id, dst.parent_id}
        obstacles = [
            _inflate(b, _CLEAR - 2) for b in boxes.values() if b.id not in (src.id, dst.id)
        ]
        obstacles += [
            _inflate(c, _PANEL_CLEAR) for c in containers.values() if c.id not in own_parents
        ]
        # Endpoint shapes block too (routes must not re-enter them), with a small pad.
        obstacles += [_inflate(src, 2.0), _inflate(dst, 2.0)]

        def blocked(ix: int, iy: int, nx: int, ny: int, xs=xs, ys=ys, obs=obstacles) -> bool:
            ax, ay, bx, by = xs[ix], ys[iy], xs[nx], ys[ny]
            return any(o.blocks(ax, ay, bx, by) for o in obs)

        path = _astar(xs, ys, (xi[sox], yi[soy]), (xi[tox], yi[toy]), blocked, used)
        if path is None:
            continue  # client falls back to a bound elbow arrow

        for i in range(len(path) - 1):  # spread later arrows off this corridor
            a_, b_ = path[i], path[i + 1]
            used.add((min(a_, b_), max(a_, b_)))

        pts = [(sx, sy), *((xs[ix], ys[iy]) for ix, iy in path), (tx_, ty_)]
        pts = _simplify(pts)
        arrow.points = [c for p in pts for c in p]

        # Label anchor: midpoint of the longest segment (labels get room to breathe).
        if arrow.text:
            longest = max(
                zip(pts, pts[1:], strict=False),
                key=lambda seg: abs(seg[1][0] - seg[0][0]) + abs(seg[1][1] - seg[0][1]),
            )
            arrow.label_x = (longest[0][0] + longest[1][0]) / 2
            arrow.label_y = (longest[0][1] + longest[1][1]) / 2

    return actions
