"""Rasterize the drawn AgentActions to a PNG so the vision Critic can *see* the diagram.

The agent-service is headless (no tldraw canvas), so we draw the same geometry the client
will render — container panels, kind-styled boxes (diamonds for decisions), arrows — using
Pillow. This is a faithful-enough preview for an LLM to judge layout quality (overlaps,
crowding, readability) — not a pixel-perfect twin of tldraw.
"""

from __future__ import annotations

import io
import math

from PIL import Image, ImageDraw, ImageFont

from app.graph.critique import elbow_path
from app.schema import AgentAction, Shape

_PAD = 60
_MAX_W = 1200
_BG = (255, 255, 255)
_BOX_FILL = (248, 250, 252)
_BOX_LINE = (51, 65, 85)
_TEXT = (15, 23, 42)
_ARROW = (99, 102, 241)

# tldraw color token → (fill tint, outline). Mirrors what the client renders so the
# vision critic judges roughly the same picture the user sees.
_TOKEN_TINTS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "blue": ((219, 234, 254), (37, 99, 235)),
    "light-blue": ((224, 242, 254), (2, 132, 199)),
    "violet": ((237, 233, 254), (124, 58, 237)),
    "orange": ((255, 237, 213), (234, 88, 12)),
    "green": ((220, 252, 231), (22, 163, 74)),
    "yellow": ((254, 249, 195), (202, 138, 4)),
    "red": ((254, 226, 226), (220, 38, 38)),
    "grey": ((241, 245, 249), (71, 85, 105)),
}

# macOS-friendly font candidates; falls back to Pillow's bitmap font if none load.
_FONT_PATHS = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "DejaVuSans.ttf",
)


def _font(size: int = 14) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _center(s: Shape) -> tuple[float, float]:
    return (s.x + s.w / 2, s.y + s.h / 2)


def _tints(s: Shape) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    return _TOKEN_TINTS.get(s.color or "", (_BOX_FILL, _BOX_LINE))


def render_actions(actions: list[AgentAction], *, scale_cap: int = _MAX_W) -> bytes:
    """Draw containers + boxes + arrows to a PNG and return its bytes (empty if nothing)."""
    boxes: dict[str, Shape] = {}
    containers: list[Shape] = []
    arrows: list[Shape] = []
    texts: list[Shape] = []
    for a in actions:
        s = a.shape
        if a.type != "create" or not s:
            continue
        if s.type == "geo":
            boxes[s.id] = s
        elif s.type == "container":
            containers.append(s)
        elif s.type == "arrow":
            arrows.append(s)
        elif s.type == "text":
            texts.append(s)

    if not boxes and not containers:
        return b""

    # World bounds → canvas transform (shift into view, then scale to fit width).
    rects = list(boxes.values()) + containers + texts
    min_x = min(s.x for s in rects)
    min_y = min(s.y for s in rects)
    max_x = max(s.x + s.w for s in rects)
    max_y = max(s.y + s.h for s in rects)
    world_w = (max_x - min_x) + 2 * _PAD
    world_h = (max_y - min_y) + 2 * _PAD
    scale = min(1.0, scale_cap / world_w)

    def tx(x: float) -> float:
        return (x - min_x + _PAD) * scale

    def ty(y: float) -> float:
        return (y - min_y + _PAD) * scale

    img = Image.new("RGB", (max(1, int(world_w * scale)), max(1, int(world_h * scale))), _BG)
    draw = ImageDraw.Draw(img)
    font = _font(max(10, int(14 * scale)))
    title_font = _font(max(11, int(16 * scale)))
    line_h = max(12, int(18 * scale))

    heading_font = _font(max(14, int(24 * scale)))
    for s in texts:  # loose text (e.g. the diagram title)
        draw.text((tx(s.x), ty(s.y)), (s.text or "")[:80], fill=_TEXT, font=heading_font)

    # Containers first (they sit under everything), then boxes, then arrows on top.
    for s in containers:
        x0, y0, x1, y1 = tx(s.x), ty(s.y), tx(s.x + s.w), ty(s.y + s.h)
        fill, line = _tints(s)
        draw.rectangle([x0, y0, x1, y1], fill=fill, outline=line, width=2)
        if s.text:
            draw.text((x0 + 10, y0 + 8), s.text[:60], fill=line, font=title_font)

    for s in boxes.values():
        x0, y0, x1, y1 = tx(s.x), ty(s.y), tx(s.x + s.w), ty(s.y + s.h)
        fill, line = _tints(s)
        if s.kind == "decision":
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            draw.polygon([(cx, y0), (x1, cy), (cx, y1), (x0, cy)], fill=fill, outline=line)
        else:
            draw.rectangle([x0, y0, x1, y1], fill=fill, outline=line, width=2)
        lines = (s.text or "").split("\n")
        if s.subtitle:
            lines.append(s.subtitle)
        for i, raw in enumerate(lines):
            line_y = y0 + 6 + i * line_h
            if line_y > y1 - line_h + 6:  # clip lines that fall outside the box
                break
            draw.text((x0 + 8, line_y), raw[:40], fill=_TEXT, font=font)

    # Draw arrows as the same approximated ELBOW routes the client renders (and the
    # geometry critic checks) — the vision critic must judge what the user will see.
    all_rects = dict(boxes)
    for c in containers:
        all_rects.setdefault(c.id, c)
    for s in arrows:
        src = all_rects.get(s.from_id or "")
        dst = all_rects.get(s.to_id or "")
        if s.points and len(s.points) >= 4:  # routed by our router — draw the real path
            pts = [(tx(x), ty(y)) for x, y in zip(s.points[::2], s.points[1::2], strict=False)]
            draw.line(pts, fill=_ARROW, width=2)
            _arrowhead(draw, pts[-2], pts[-1])
        elif src and dst:
            path = elbow_path(src, dst)
            pts = [(tx(path[0][0][0]), ty(path[0][0][1]))]
            pts += [(tx(x), ty(y)) for (_a, (x, y)) in path]
            draw.line(pts, fill=_ARROW, width=2)
            _arrowhead(draw, pts[-2], pts[-1])
        else:  # unbound: short stub at the arrow's own coords
            p0 = (tx(s.x), ty(s.y))
            p1 = (tx(s.x + 120), ty(s.y))
            draw.line([p0, p1], fill=_ARROW, width=2)
            _arrowhead(draw, p0, p1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _arrowhead(draw: ImageDraw.ImageDraw, p0: tuple, p1: tuple, size: int = 9) -> None:
    """Draw a small filled triangle at p1 pointing away from p0."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    dist = math.hypot(dx, dy) or 1.0
    ux, uy = dx / dist, dy / dist  # unit direction
    # base of the head, `size` back along the line; two wings perpendicular to it
    bx, by = p1[0] - ux * size, p1[1] - uy * size
    px, py = -uy, ux
    left = (bx + px * size * 0.6, by + py * size * 0.6)
    right = (bx - px * size * 0.6, by - py * size * 0.6)
    draw.polygon([p1, left, right], fill=_ARROW)
