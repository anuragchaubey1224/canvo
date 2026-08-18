"""Diagram composition — panels justified into a column grid inside a titled frame.

Eraser's diagrams read like posters, not like flowcharts that grew. Everything sits inside
one bounded, titled frame; the phase panels are packed into a **column grid** where each
panel spans one or two columns; every row is filled edge to edge and every panel in a row
shares that row's height. Nothing floats and no row ends in a void.

Measured from the reference (JWT workflow, actual units): frame 1708x1414 — aspect 1.21 —
holding a full-width row, then a 752 + 792 split row, then another full-width row, with row
heights 376 / 400 / 392. Our previous greedy packer wrapped panels at a width cap and kept
whatever slack fell out, so the same 5/4/1/3-node plan composed at **5.9:1** with one panel
alone in a half-empty row. That single difference — free packing versus a justified grid —
was most of the visual gap.

This module owns only the arithmetic of *where the boxes go*. The caller sizes each cell
(by laying its members out) and draws the result; nothing here knows about shapes, plans or
tldraw. The frame's padding is deliberately wider than a card gap: it is also the corridor
the arrow router uses for long cross-panel runs, the way the reference routes its
"token in hand" arrow down the left margin.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Frame border → panel grid. Wider than a card gap on purpose: this band is the corridor
# the arrow router takes long cross-panel runs through, so it has to comfortably contain
# route.py's `_MARGIN` or those arrows draw on top of the frame's own border.
FRAME_PAD = 72.0
FRAME_TITLE_H = 64.0  # header band holding the diagram title
PANEL_GAP_X = 52.0
PANEL_GAP_Y = 56.0

_COLS = 2  # the reference composition is a two-column grid
_COL_MIN = 280.0  # a column narrower than one card + panel padding isn't worth splitting
_TARGET_ASPECT = 1.35  # the reference's grid is 1596x1220; anything near 1.3 reads as a poster
_MAX_STRETCH = 1.8  # how far a lone cell may be widened to justify its row


@dataclass(frozen=True)
class Cell:
    """Something to place: a group panel (`chrome`) or a bare ungrouped node.

    `w`/`h` are the cell's NATURAL outer size — what it needs if nothing stretched it.
    """

    key: str
    w: float
    h: float
    chrome: bool = True


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class Grid:
    columns: int
    column_width: float
    content_width: float


@dataclass(frozen=True)
class Composition:
    frame: Box
    slots: dict[str, Box]  # final (stretched) box per cell key
    grid: Grid


def _spans(cells: list[Cell], grid: Grid) -> dict[str, int]:
    return {c.key: (grid.columns if c.w > grid.column_width + 1 else 1) for c in cells}


def _pack(cells: list[Cell], grid: Grid) -> list[list[Cell]]:
    """Cells in order into rows, wrapping when the row's spans fill the grid."""
    span = _spans(cells, grid)
    rows: list[list[Cell]] = []
    row: list[Cell] = []
    used = 0
    for cell in cells:
        if row and used + span[cell.key] > grid.columns:
            rows.append(row)
            row, used = [], 0
        row.append(cell)
        used += span[cell.key]
    if row:
        rows.append(row)
    return rows


def _grid_for(cells: list[Cell], content_w: float, gap: float) -> Grid:
    if len(cells) < 2 or content_w < 2 * _COL_MIN + gap:
        return Grid(1, content_w, content_w)
    return Grid(_COLS, (content_w - gap) / _COLS, content_w)


def choose_grid(cells: list[Cell], gap_scale: float = 1.0) -> Grid:
    """Pick the grid whose composition reads closest to a poster.

    The width can't come from the widest panel alone: four narrow panels would then stack
    into one tall column, while one very wide panel would blow the columns out so far that
    its neighbours float in empty space. So we score the plausible widths — every panel at
    full span, and every panel at half span — against how close the finished grid lands to
    `_TARGET_ASPECT` and how much of it the panels actually fill.

    Exposed separately from `compose` so the caller can tighten a slightly-too-wide panel
    into one column *before* the final placement, and then pin the same grid.
    """
    if not cells:
        return Grid(1, 0.0, 0.0)
    gap = PANEL_GAP_X * gap_scale
    gap_y = PANEL_GAP_Y * gap_scale
    widest = max(c.w for c in cells)
    natural_area = sum(c.w * c.h for c in cells)

    candidates = {widest} | {max(widest, 2 * c.w + gap) for c in cells}
    best: tuple[float, Grid] | None = None
    for content_w in sorted(candidates):
        grid = _grid_for(cells, content_w, gap)
        rows = _pack(cells, grid)
        height = sum(max(c.h for c in r) for r in rows) + gap_y * (len(rows) - 1)
        if height <= 0:
            continue
        aspect_miss = abs(math.log((content_w / height) / _TARGET_ASPECT))
        waste = 1.0 - natural_area / (content_w * height)
        score = aspect_miss + waste
        if best is None or score < best[0]:
            best = (score, grid)
    return best[1] if best else _grid_for(cells, widest, gap)


def compose(
    cells: list[Cell],
    *,
    gap_scale: float = 1.0,
    origin: tuple[float, float] = (0.0, 0.0),
    grid: Grid | None = None,
) -> Composition:
    """Place `cells` in order into a justified grid and wrap the result in a frame."""
    grid = grid or choose_grid(cells, gap_scale)
    cols, col_w, content_w = grid.columns, grid.column_width, grid.content_width
    gap_x = PANEL_GAP_X * gap_scale
    gap_y = PANEL_GAP_Y * gap_scale

    span = _spans(cells, grid)
    rows = _pack(cells, grid)

    ox, oy = origin
    slots: dict[str, Box] = {}
    y = oy
    for placed_row in rows:
        row_h = max(c.h for c in placed_row)
        if sum(span[c.key] for c in placed_row) < cols:
            # A short row would otherwise leave a void beside it, so its cells share the
            # full width — but only up to `_MAX_STRETCH`. Blowing a one-card panel out to
            # the whole grid leaves the card marooned in an empty box; past that point a
            # narrower panel, centred, reads as deliberate.
            share = (content_w - gap_x * (len(placed_row) - 1)) / len(placed_row)
            widths = [min(share, c.w * _MAX_STRETCH) for c in placed_row]
        else:
            widths = [col_w * span[c.key] + gap_x * (span[c.key] - 1) for c in placed_row]
        used_w = sum(widths) + gap_x * (len(placed_row) - 1)
        x = ox + (content_w - used_w) / 2
        for cell, w in zip(placed_row, widths, strict=False):
            slots[cell.key] = Box(x, y, w, row_h)
            x += w + gap_x
        y += row_h + gap_y

    grid_h = (y - gap_y) - oy if rows else 0.0
    frame = Box(
        ox - FRAME_PAD,
        oy - FRAME_TITLE_H,
        content_w + 2 * FRAME_PAD,
        grid_h + FRAME_TITLE_H + FRAME_PAD,
    )
    return Composition(frame=frame, slots=slots, grid=grid)


def center_in(box: Box, w: float, h: float, *, top_inset: float = 0.0, bottom_inset: float = 0.0):
    """Origin that centres a `w`x`h` block inside `box`, below any title band."""
    avail_h = box.h - top_inset - bottom_inset
    return (
        box.x + (box.w - w) / 2,
        box.y + top_inset + max(0.0, (avail_h - h) / 2),
    )
