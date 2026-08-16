"""Geometric self-check for a drawn diagram — the deterministic half of the Critic.

No LLM, no cost, fully testable offline. It looks at the concrete `AgentAction`s the
Drawer emitted (box rects, container panels, arrows) and reports layout defects the
agent can fix by relaying out:

  - **overlap**            two sibling boxes (same container scope) overlap or crowd,
                           two containers collide, or a box bleeds into a container it
                           doesn't belong to
  - **container_overflow** a box assigned to a container is not fully inside it
  - **dangling_arrow**     an arrow endpoint references a shape that was never created

The Critic node turns these into a refine decision: `overlap` is the reliable trigger
(spacing is the lever we can pull); the other kinds are surfaced as real bugs but more
spacing wouldn't fix them.

Pairs with `critic_vision.py` (the LLM half): geometry guarantees a reliable, convergent
loop; vision catches the fuzzy, semantic problems geometry can't see.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schema import AgentAction, Shape

# A box wants at least this much clear space around it. Two boxes whose rects — grown
# by this margin — still intersect are "crowded", even if they don't literally overlap.
_MARGIN = 28.0

# Slack when checking a member sits inside its container (float noise, border widths).
_INSET_EPS = 0.5


class Issue(BaseModel):
    kind: str  # "overlap" | "container_overflow" | "dangling_arrow"
    severity: str = "warning"  # "error" | "warning"
    message: str
    shape_ids: list[str] = Field(default_factory=list)


class GeometryReport(BaseModel):
    issues: list[Issue] = Field(default_factory=list)
    max_box_height: float = 0.0

    @property
    def has_overlap(self) -> bool:
        return any(i.kind == "overlap" for i in self.issues)


def _created(actions: list[AgentAction], shape_type: str) -> list[Shape]:
    return [
        a.shape for a in actions if a.type == "create" and a.shape and a.shape.type == shape_type
    ]


def _intersects(a: Shape, b: Shape, pad: float) -> bool:
    """Do the two rects intersect once each is grown by `pad` on every side?"""
    return (
        a.x - pad < b.x + b.w + pad
        and a.x + a.w + pad > b.x - pad
        and a.y - pad < b.y + b.h + pad
        and a.y + a.h + pad > b.y - pad
    )


def _inside(inner: Shape, outer: Shape) -> bool:
    return (
        inner.x >= outer.x - _INSET_EPS
        and inner.y >= outer.y - _INSET_EPS
        and inner.x + inner.w <= outer.x + outer.w + _INSET_EPS
        and inner.y + inner.h <= outer.y + outer.h + _INSET_EPS
    )


def _overlap(a: Shape, b: Shape, what: str) -> Issue:
    return Issue(
        kind="overlap",
        severity="error",
        message=f"{what} '{a.id}' and '{b.id}' overlap or crowd",
        shape_ids=[a.id, b.id],
    )


Point = tuple[float, float]
Segment = tuple[Point, Point]


def elbow_path(a: Shape, b: Shape) -> list[Segment]:
    """Approximate the client's elbow route between two shapes as axis-aligned segments.

    Mirrors the client's facing-edge anchors: exit/enter on the side pointing at the
    other shape, with one bend at the midpoint of the dominant axis. Used by the
    crossing check below and by the vision-critic renderer, so what the critic judges
    matches what the user actually sees.
    """
    acx, acy = a.x + a.w / 2, a.y + a.h / 2
    bcx, bcy = b.x + b.w / 2, b.y + b.h / 2
    dx, dy = bcx - acx, bcy - acy

    if abs(dx) >= abs(dy):  # horizontal-dominant: right/left edges, bend at mid-x
        x0 = a.x + a.w if dx >= 0 else a.x
        x1 = b.x if dx >= 0 else b.x + b.w
        mid = (x0 + x1) / 2
        return [
            ((x0, acy), (mid, acy)),
            ((mid, acy), (mid, bcy)),
            ((mid, bcy), (x1, bcy)),
        ]
    y0 = a.y + a.h if dy >= 0 else a.y  # vertical-dominant: bottom/top edges
    y1 = b.y if dy >= 0 else b.y + b.h
    mid = (y0 + y1) / 2
    return [
        ((acx, y0), (acx, mid)),
        ((acx, mid), (bcx, mid)),
        ((bcx, mid), (bcx, y1)),
    ]


def _segment_hits_rect(seg: Segment, r: Shape, inset: float = 4.0) -> bool:
    """Does an axis-aligned segment pass through the rect (shrunk by `inset`)?"""
    (x1, y1), (x2, y2) = seg
    lo_x, hi_x = min(x1, x2), max(x1, x2)
    lo_y, hi_y = min(y1, y2), max(y1, y2)
    return (
        lo_x < r.x + r.w - inset
        and hi_x > r.x + inset
        and lo_y < r.y + r.h - inset
        and hi_y > r.y + inset
    )


def analyze_geometry(actions: list[AgentAction]) -> GeometryReport:
    """Inspect the drawn actions and report layout defects (deterministic, no LLM)."""
    boxes = _created(actions, "geo")
    containers = _created(actions, "container")
    container_by_id = {c.id: c for c in containers}
    issues: list[Issue] = []

    # 1) crowded / overlapping boxes — only within the same container scope: a member
    #    sitting on top of its own container is intentional, siblings colliding is not.
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if (a.parent_id or "") == (b.parent_id or "") and _intersects(a, b, _MARGIN):
                issues.append(_overlap(a, b, "boxes"))

    # 2) container panels colliding with each other.
    for i in range(len(containers)):
        for j in range(i + 1, len(containers)):
            if _intersects(containers[i], containers[j], _MARGIN):
                issues.append(_overlap(containers[i], containers[j], "containers"))

    # 3) membership: a box must sit inside its own container, and must not bleed into
    #    a container it doesn't belong to.
    for s in boxes:
        own = container_by_id.get(s.parent_id or "")
        if own is not None and not _inside(s, own):
            issues.append(
                Issue(
                    kind="container_overflow",
                    severity="error",
                    message=f"box '{s.id}' is not fully inside its container '{own.id}'",
                    shape_ids=[s.id, own.id],
                )
            )
        for c in containers:
            if c.id != (s.parent_id or "") and _intersects(s, c, 0.0):
                issues.append(_overlap(s, c, "box and foreign container"))

    # 4) dangling arrows — an endpoint points at a shape that was never created.
    box_by_id = {s.id: s for s in boxes}
    valid_ids = set(box_by_id) | set(container_by_id)
    arrows = [
        a.shape for a in actions if a.type == "create" and a.shape and a.shape.type == "arrow"
    ]
    for arrow in arrows:
        for end in (arrow.from_id, arrow.to_id):
            if end and end not in valid_ids:
                issues.append(
                    Issue(
                        kind="dangling_arrow",
                        severity="error",
                        message=f"arrow '{arrow.id}' points at missing shape '{end}'",
                        shape_ids=[arrow.id],
                    )
                )

    # 5) arrow crossings — approximate each bound arrow's elbow route and flag segments
    #    that cut through a panel or box neither endpoint belongs to. Spacing can't fix
    #    these (warning, not a refine trigger), but the report keeps the critic honest —
    #    "layout is clean" must mean what the user sees is clean.
    label_points: list[tuple[str, float, float]] = []
    for arrow in arrows:
        src = box_by_id.get(arrow.from_id or "")
        dst = box_by_id.get(arrow.to_id or "")
        if not src or not dst:
            continue
        if arrow.points and len(arrow.points) >= 4:  # routed by our router — judge the real path
            pts = list(zip(arrow.points[::2], arrow.points[1::2], strict=False))
            path = list(zip(pts, pts[1:], strict=False))
        else:
            path = elbow_path(src, dst)
        if arrow.text:
            if arrow.label_x is not None and arrow.label_y is not None:
                label_points.append((arrow.id, arrow.label_x, arrow.label_y))
            else:
                (mx1, my1), (mx2, my2) = path[len(path) // 2]
                label_points.append((arrow.id, (mx1 + mx2) / 2, (my1 + my2) / 2))
        endpoint_ids = {src.id, dst.id}
        own_parents = {src.parent_id, dst.parent_id}
        obstacles = [c for c in containers if c.id not in own_parents] + [
            s for s in boxes if s.id not in endpoint_ids
        ]
        hit = next((o for o in obstacles if any(_segment_hits_rect(seg, o) for seg in path)), None)
        if hit is not None:
            issues.append(
                Issue(
                    kind="arrow_crossing",
                    severity="warning",
                    message=f"arrow '{arrow.id}' routes through '{hit.id}'",
                    shape_ids=[arrow.id, hit.id],
                )
            )

    # 6) label collisions — two edge labels landing on nearly the same spot.
    for i in range(len(label_points)):
        for j in range(i + 1, len(label_points)):
            id_a, xa, ya = label_points[i]
            id_b, xb, yb = label_points[j]
            if abs(xa - xb) < 56 and abs(ya - yb) < 24:
                issues.append(
                    Issue(
                        kind="label_collision",
                        severity="warning",
                        message=f"labels of '{id_a}' and '{id_b}' overlap",
                        shape_ids=[id_a, id_b],
                    )
                )

    max_h = max((s.h for s in boxes), default=0.0)
    return GeometryReport(issues=issues, max_box_height=max_h)


def geometry_summary(report: GeometryReport) -> str:
    """One-line human summary for the critique event / logs."""
    if not report.issues:
        return "layout is clean"
    counts: dict[str, int] = {}
    for i in report.issues:
        counts[i.kind] = counts.get(i.kind, 0) + 1
    names = {
        "overlap": ("overlap", "overlaps"),
        "container_overflow": ("container overflow", "container overflows"),
        "dangling_arrow": ("dangling arrow", "dangling arrows"),
        "arrow_crossing": ("arrow crossing", "arrow crossings"),
        "label_collision": ("label collision", "label collisions"),
    }
    parts = []
    for kind, n in counts.items():
        one, many = names.get(kind, (kind, kind))
        parts.append(f"{n} {one if n == 1 else many}")
    return ", ".join(parts)
