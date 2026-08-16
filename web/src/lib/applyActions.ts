// Maps AgentActions from the service onto the tldraw canvas.
// This is our thin "action-apply" layer — we own the tldraw SDK directly.

import { createShapeId, toRichText, type Editor } from 'tldraw'
import type { AgentAction, Shape } from './types'

type Box = { x: number; y: number; w: number; h: number }

/** Returns a stateful applier that remembers box geometry so it can route arrows. */
export function makeApplier(editor: Editor) {
  const boxes = new Map<string, Box>()

  return (action: AgentAction) => {
    if (action.type === 'delete' && action.shape_id) {
      editor.deleteShape(createShapeId(action.shape_id))
      return
    }

    const s = action.shape
    if (!s) return

    if (s.type === 'arrow') {
      createArrow(editor, boxes, s)
      return
    }

    // geo box (default)
    const w = s.w || 160
    const h = s.h || 80
    boxes.set(s.id, { x: s.x, y: s.y, w, h })
    editor.createShape({
      id: createShapeId(s.id),
      type: 'geo',
      x: s.x,
      y: s.y,
      props: {
        geo: 'rectangle',
        w,
        h,
        richText: toRichText(s.text ?? ''),
        size: 's',
        align: 'start',
        verticalAlign: 'start',
      },
    })
  }
}

function createArrow(editor: Editor, boxes: Map<string, Box>, s: Shape) {
  const from = s.from_id ? boxes.get(s.from_id) : undefined
  const to = s.to_id ? boxes.get(s.to_id) : undefined
  // Route from the right edge of the source box to the left edge of the target box.
  const start = from ? { x: from.x + from.w, y: from.y + from.h / 2 } : { x: s.x, y: s.y }
  const end = to ? { x: to.x, y: to.y + to.h / 2 } : { x: s.x + 120, y: s.y }

  editor.createShape({
    id: createShapeId(s.id),
    type: 'arrow',
    x: 0,
    y: 0,
    props: { start, end, richText: toRichText(s.text ?? '') },
  })
}
