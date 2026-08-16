// Maps AgentActions from the service onto the tldraw canvas.
// This is our thin "action-apply" layer — we own the tldraw SDK directly.

import { createShapeId, toRichText, type Editor } from 'tldraw'
import type { AgentAction, Shape } from './types'

export function makeApplier(editor: Editor) {
  return (action: AgentAction) => {
    if (action.type === 'delete' && action.shape_id) {
      editor.deleteShape(createShapeId(action.shape_id))
      return
    }

    const s = action.shape
    if (!s) return

    if (s.type === 'arrow') {
      createArrow(editor, s)
      return
    }

    // geo box (default)
    editor.createShape({
      id: createShapeId(s.id),
      type: 'geo',
      x: s.x,
      y: s.y,
      props: {
        geo: 'rectangle',
        w: s.w || 160,
        h: s.h || 80,
        richText: toRichText(s.text ?? ''),
        size: 's',
        align: 'start',
        verticalAlign: 'start',
      },
    })
  }
}

function createArrow(editor: Editor, s: Shape) {
  const fromId = s.from_id ? createShapeId(s.from_id) : undefined
  const toId = s.to_id ? createShapeId(s.to_id) : undefined
  // Read the ACTUAL rendered bounds (tldraw grows boxes to fit text), so the
  // arrow connects real edges instead of our estimated geometry.
  const a = fromId ? editor.getShapePageBounds(fromId) : undefined
  const b = toId ? editor.getShapePageBounds(toId) : undefined

  let start = { x: s.x, y: s.y }
  let end = { x: s.x + 120, y: s.y }
  if (a && b) {
    if (b.minX >= a.maxX) {
      start = { x: a.maxX, y: a.center.y }
      end = { x: b.minX, y: b.center.y }
    } else if (b.maxX <= a.minX) {
      start = { x: a.minX, y: a.center.y }
      end = { x: b.maxX, y: b.center.y }
    } else {
      start = { x: a.center.x, y: a.maxY }
      end = { x: b.center.x, y: b.minY }
    }
  }

  editor.createShape({
    id: createShapeId(s.id),
    type: 'arrow',
    x: 0,
    y: 0,
    props: { start, end, richText: toRichText(s.text ?? '') },
  })
}
