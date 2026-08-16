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
} from 'tldraw'
import type { ConnectorShape } from '../shapes/ConnectorUtil'
import type { NodeCardShape } from '../shapes/NodeCardUtil'
import type { PanelShape } from '../shapes/PanelUtil'
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

export function makeApplier(editor: Editor) {
  return (action: AgentAction) => {
    if (action.type === 'delete' && action.shape_id) {
      editor.deleteShape(createShapeId(action.shape_id))
      return
    }

    const s = action.shape
    if (!s) return

    if (s.type === 'arrow') {
      // Routed by our obstacle-avoiding router → authoritative connector polyline;
      // unrouted arrows fall back to tldraw's bound elbow arrows.
      if (s.points && s.points.length >= 4) createConnector(editor, s)
      else createArrow(editor, s)
      return
    }

    if (s.type === 'container') {
      createPanel(editor, s)
      return
    }

    if (s.type === 'text') {
      createText(editor, s)
      return
    }

    createNode(editor, s)
  }
}

// A group panel (Eraser-style swimlane): our custom 'panel' shape. Created before its
// members (stream order), so it naturally sits under them.
function createPanel(editor: Editor, s: Shape) {
  editor.createShape<PanelShape>({
    id: createShapeId(s.id),
    type: 'panel',
    x: s.x,
    y: s.y,
    props: {
      w: s.w || 480,
      h: s.h || 320,
      title: s.text ?? '',
      accent: color(s, 'grey'),
    },
  })
}

// Loose text — the diagram title heading.
function createText(editor: Editor, s: Shape) {
  editor.createShape({
    id: createShapeId(s.id),
    type: 'text',
    x: s.x,
    y: s.y,
    props: { richText: toRichText(s.text ?? ''), size: 'l' },
  })
}

function createNode(editor: Editor, s: Shape) {
  // Semantic nodes render as our custom node-card (icon + title + subtitle; diamond
  // for decisions, cylinder for datastores). Kindless boxes (ERD tables, endpoint
  // lists) keep the plain top-left multi-line geo layout.
  if (s.kind || s.subtitle) {
    editor.createShape<NodeCardShape>({
      id: createShapeId(s.id),
      type: 'node-card',
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
    })
    return
  }

  editor.createShape({
    id: createShapeId(s.id),
    type: 'geo',
    x: s.x,
    y: s.y,
    props: {
      geo: (s.kind && KIND_GEO[s.kind]) || 'rectangle',
      w: s.w || 160,
      h: s.h || 80,
      color: color(s),
      fill: 'none',
      richText: toRichText(s.text ?? ''),
      size: 's',
      align: 'start',
      verticalAlign: 'start',
    },
  })
}

// Server-routed connector: waypoints come in absolute coords; the shape's origin is the
// first point and props store the rest relative to it.
function createConnector(editor: Editor, s: Shape) {
  const flat = s.points as number[]
  const ox = flat[0]
  const oy = flat[1]
  const rel: number[] = []
  for (let i = 0; i + 1 < flat.length; i += 2) rel.push(flat[i] - ox, flat[i + 1] - oy)
  editor.createShape<ConnectorShape>({
    id: createShapeId(s.id),
    type: 'connector',
    x: ox,
    y: oy,
    props: {
      points: rel,
      accent: color(s, 'grey'),
      label: s.text ?? '',
      labelX: (s.label_x ?? ox) - ox,
      labelY: (s.label_y ?? oy) - oy,
    },
  })
}

// Arrows use REAL tldraw bindings (not fixed points): tldraw routes them to the shape
// edges itself and keeps them attached when the user drags nodes around. Elbow kind
// gives the orthogonal routing Eraser-style diagrams read with. We pin each terminal
// to the FACING edge of its shape (precise anchors) so elbows leave/enter from the
// side that points at the other node — center-anchored routing let long arrows cut
// straight through neighboring cards.
let labelSlot = 0 // stagger label positions so adjacent edge labels don't overlap

function createArrow(editor: Editor, s: Shape) {
  const arrowId = createShapeId(s.id)
  const hasLabel = Boolean(s.text)
  editor.createShape({
    id: arrowId,
    type: 'arrow',
    x: s.x,
    y: s.y,
    props: {
      kind: 'elbow',
      start: { x: 0, y: 0 },
      end: { x: 120, y: 0 },
      richText: toRichText(s.text ?? ''),
      size: 's',
      scale: 0.8, // compact labels/arrowheads — matched to the dense card layout
      color: color(s),
      labelColor: color(s),
      labelPosition: hasLabel ? [0.5, 0.35, 0.65][labelSlot++ % 3] : 0.5,
    },
  })

  const fromId = s.from_id ? createShapeId(s.from_id) : undefined
  const toId = s.to_id ? createShapeId(s.to_id) : undefined
  const a = fromId && editor.getShape(fromId) ? editor.getShapePageBounds(fromId) : undefined
  const b = toId && editor.getShape(toId) ? editor.getShapePageBounds(toId) : undefined

  // Facing-edge anchors: pick the side of each shape that points toward the other.
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
      props: {
        terminal,
        normalizedAnchor: anchor,
        isExact: false,
        isPrecise: precise,
      },
    })
  }
  bind('start', fromId, startAnchor)
  bind('end', toId, endAnchor)
}
