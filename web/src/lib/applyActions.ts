// Maps AgentActions from the service onto the tldraw canvas.
// This is our thin "action-apply" layer — we own the tldraw SDK directly.
//
// Shape semantics (ADR-013): the service sends an OPEN-set `kind` plus generic props
// (subtitle, color, parent_id). Known kinds get a specific tldraw geo; anything unknown
// falls back to a plain rectangle, so new server-side kinds never break this client.

import {
  createShapeId,
  toRichText,
  type Editor,
  type TLDefaultColorStyle,
  type TLGeoShape,
  type TLShapePartial,
} from 'tldraw'
import type { AgentAction, Shape } from './types'

type GeoStyle = TLGeoShape['props']['geo']

// tldraw's valid color tokens — guard against a planner/server slip.
const COLOR_TOKENS = new Set<string>([
  'black', 'grey', 'light-violet', 'violet', 'blue', 'light-blue',
  'yellow', 'orange', 'green', 'light-green', 'light-red', 'red', 'white',
] satisfies TLDefaultColorStyle[])

// Semantic kind → tldraw geo. Unknown kinds render as rectangles (open set).
const KIND_GEO: Record<string, GeoStyle> = {
  decision: 'diamond',
  start: 'ellipse',
  end: 'ellipse',
  external: 'cloud',
}

function color(s: Shape, fallback: TLDefaultColorStyle = 'black'): TLDefaultColorStyle {
  return s.color && COLOR_TOKENS.has(s.color) ? (s.color as TLDefaultColorStyle) : fallback
}

/** Marks the shapes we own. Anything the user drew themselves has no such stamp, so a
 *  regeneration can sweep away its own leftovers without touching their work. */
const OURS = { canvo: true }

function isOurs(shape: { meta?: Record<string, unknown> }): boolean {
  return shape.meta?.canvo === true
}

export interface Applier {
  /** Create or update one shape from a streamed action. */
  apply(action: AgentAction): void
  /** Start a fresh pass (a Critic refine re-emits the whole diagram). */
  restart(): void
  /** Remove the shapes we drew last time that this run didn't re-emit. */
  finish(): void
}

/** A reconciler, not a painter.
 *
 * The old applier only created, so every run had to clear the canvas first — which threw
 * away the camera, the selection, and anything the user had drawn themselves. Now each
 * incoming shape updates the one already there when the id matches (our ids are
 * deterministic, so a node that survives an edit keeps its identity) and only what has
 * genuinely gone is deleted. An edit that touches two nodes now moves two nodes. */
export function makeApplier(editor: Editor): Applier {
  const seen = new Set<string>()

  return {
    restart() {
      seen.clear()
    },

    apply(action: AgentAction) {
      if (action.type === 'delete' && action.shape_id) {
        editor.deleteShape(createShapeId(action.shape_id))
        return
      }

      const s = action.shape
      if (!s) return
      seen.add(s.id)

      const id = createShapeId(s.id)
      const existing = editor.getShape(id)
      // Each builder returns a well-formed shape for its own type, but TypeScript can't
      // correlate `type` with `props` across the union inside tldraw's overloads — hence
      // the one cast, rather than seven near-identical branches.
      const built = { id, ...build(s) } as TLShapePartial

      if (existing && existing.type === built.type) {
        // Same shape, new geometry or props — patch it, so tldraw animates the move and
        // the user's selection and camera survive.
        editor.updateShape(built)
        return
      }
      if (existing) editor.deleteShape(id) // the kind changed; a box became a cylinder
      editor.createShape({ ...built, meta: OURS })

      // Arrows carry bindings, which only make sense on a freshly created arrow.
      if (s.type === 'arrow' && !(s.points && s.points.length >= 4)) bindArrow(editor, s, id)
    },

    finish() {
      const stale = editor
        .getCurrentPageShapes()
        .filter((shape) => isOurs(shape) && !seen.has(String(shape.id).replace(/^shape:/, '')))
        .map((shape) => shape.id)
      if (stale.length) editor.deleteShapes(stale)
    },
  }
}

/** One streamed shape → the tldraw shape to create or patch. */
function build(s: Shape) {
  if (s.type === 'arrow') {
    return s.points && s.points.length >= 4 ? connector(s) : arrow(s)
  }
  if (s.type === 'frame') return frame(s)
  if (s.type === 'container') return panel(s)
  if (s.type === 'text') return text(s)
  return node(s)
}

// --- builders: one streamed shape → the tldraw shape to create or patch ------------------

// The outer frame: one titled box around the whole composition. Streamed first, so it
// sits under everything else.
function frame(s: Shape) {
  return {
    type: 'frame' as const,
    x: s.x,
    y: s.y,
    props: { w: s.w || 960, h: s.h || 640, title: s.text ?? '' },
  }
}

// A group panel (Eraser-style swimlane). Created before its members (stream order), so it
// naturally sits under them.
function panel(s: Shape) {
  return {
    type: 'panel' as const,
    x: s.x,
    y: s.y,
    props: { w: s.w || 480, h: s.h || 320, title: s.text ?? '', accent: color(s, 'grey') },
  }
}

// Loose text — a standalone heading.
function text(s: Shape) {
  return {
    type: 'text' as const,
    x: s.x,
    y: s.y,
    props: { richText: toRichText(s.text ?? ''), size: 'l' as const },
  }
}

function node(s: Shape) {
  // Semantic nodes render as our custom node-card (icon + title + subtitle; diamond for
  // decisions, cylinder for datastores). Kindless boxes (ERD tables, endpoint lists) keep
  // the plain top-left multi-line geo layout.
  if (s.kind || s.subtitle) {
    return {
      type: 'node-card' as const,
      x: s.x,
      y: s.y,
      props: {
        w: s.w || 240,
        h: s.h || 88,
        title: s.text ?? '',
        subtitle: s.subtitle ?? '',
        kind: s.kind ?? '',
        accent: color(s, 'grey'),
        icon: s.icon ?? '',
      },
    }
  }
  return {
    type: 'geo' as const,
    x: s.x,
    y: s.y,
    props: {
      geo: (s.kind && KIND_GEO[s.kind]) || 'rectangle',
      w: s.w || 160,
      h: s.h || 80,
      color: color(s),
      fill: 'none' as const,
      richText: toRichText(s.text ?? ''),
      size: 's' as const,
      align: 'start' as const,
      verticalAlign: 'start' as const,
    },
  }
}

// Server-routed connector: waypoints arrive in absolute coords; the shape's origin is the
// first point and props store the rest relative to it.
function connector(s: Shape) {
  const flat = s.points as number[]
  const ox = flat[0]
  const oy = flat[1]
  const rel: number[] = []
  for (let i = 0; i + 1 < flat.length; i += 2) rel.push(flat[i] - ox, flat[i + 1] - oy)
  return {
    type: 'connector' as const,
    x: ox,
    y: oy,
    props: {
      points: rel,
      accent: color(s, 'grey'),
      label: s.text ?? '',
      labelX: (s.label_x ?? ox) - ox,
      labelY: (s.label_y ?? oy) - oy,
    },
  }
}

// Arrows the router couldn't solve fall back to tldraw's own elbow routing, bound to both
// shapes so they stay attached when a card is dragged.
let labelSlot = 0 // stagger label positions so adjacent edge labels don't overlap

function arrow(s: Shape) {
  const hasLabel = Boolean(s.text)
  return {
    type: 'arrow' as const,
    x: s.x,
    y: s.y,
    props: {
      kind: 'elbow' as const,
      start: { x: 0, y: 0 },
      end: { x: 120, y: 0 },
      richText: toRichText(s.text ?? ''),
      size: 's' as const,
      scale: 0.8, // compact labels/arrowheads — matched to the dense card layout
      color: color(s),
      labelColor: color(s),
      labelPosition: hasLabel ? [0.5, 0.35, 0.65][labelSlot++ % 3] : 0.5,
    },
  }
}

/** Bindings for a fallback elbow arrow. Only meaningful on a freshly created one — an
 *  existing arrow already carries its bindings, and tldraw re-routes it itself. */
function bindArrow(editor: Editor, s: Shape, arrowId: ReturnType<typeof createShapeId>) {
  const fromId = s.from_id ? createShapeId(s.from_id) : undefined
  const toId = s.to_id ? createShapeId(s.to_id) : undefined
  const a = fromId && editor.getShape(fromId) ? editor.getShapePageBounds(fromId) : undefined
  const b = toId && editor.getShape(toId) ? editor.getShapePageBounds(toId) : undefined

  // Facing-edge anchors: pick the side of each shape that points toward the other, so an
  // elbow leaves from the side facing its destination instead of cutting across cards.
  let startAnchor = { x: 0.5, y: 0.5 }
  let endAnchor = { x: 0.5, y: 0.5 }
  const precise = Boolean(a && b)
  if (a && b) {
    const dx = b.center.x - a.center.x
    const dy = b.center.y - a.center.y
    if (Math.abs(dx) >= Math.abs(dy)) {
      startAnchor = { x: dx >= 0 ? 1 : 0, y: 0.5 }
      endAnchor = { x: dx >= 0 ? 0 : 1, y: 0.5 }
    } else {
      startAnchor = { x: 0.5, y: dy >= 0 ? 1 : 0 }
      endAnchor = { x: 0.5, y: dy >= 0 ? 0 : 1 }
    }
  }

  const bind = (
    terminal: 'start' | 'end',
    targetId: ReturnType<typeof createShapeId> | undefined,
    anchor: { x: number; y: number },
  ) => {
    if (!targetId || !editor.getShape(targetId)) return
    editor.createBinding({
      type: 'arrow',
      fromId: arrowId,
      toId: targetId,
      props: { terminal, normalizedAnchor: anchor, isExact: false, isPrecise: precise },
    })
  }
  bind('start', fromId, startAnchor)
  bind('end', toId, endAnchor)
}
