// The tool strip, moved to the left edge and stood upright.
//
// tldraw's default toolbar floats across the bottom-centre of the canvas, which on a wide
// diagram is exactly where the diagram wants to be. On the left edge it costs a 44px
// gutter and never crosses the drawing.
//
// Rendered through a portal so its position doesn't depend on tldraw's internal layout
// slots — a portal keeps React context, so the editor hooks below still work normally.

import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  TldrawUiButton,
  TldrawUiButtonIcon,
  useIsToolSelected,
  useTools,
  useTranslation,
  type TLUiIconType,
  type TLUiToolItem,
} from 'tldraw'
import { StylePanelToggle } from './StylePanelToggle'

// Grouped by what they do, separated by a hairline. Ids that a future tldraw renames are
// filtered out rather than crashing the strip.
const GROUPS: string[][] = [
  ['select', 'hand'],
  ['draw', 'eraser'],
  ['arrow', 'line'],
  ['text', 'note'],
  ['rectangle', 'ellipse', 'frame', 'asset'],
]

function ToolButton({ tool }: { tool: TLUiToolItem }) {
  const selected = useIsToolSelected(tool)
  const msg = useTranslation()
  const label = msg(tool.label)
  return (
    <TldrawUiButton
      type="tool"
      isActive={selected}
      title={label}
      aria-label={label}
      aria-pressed={selected}
      onClick={() => tool.onSelect('toolbar')}
    >
      <TldrawUiButtonIcon icon={tool.icon as TLUiIconType} />
    </TldrawUiButton>
  )
}

/** Which flyout is showing. One at a time — two panels off a 44px rail would collide. */
type Panel = 'more' | 'style' | null

export function VerticalToolbar() {
  const tools = useTools()
  const [host, setHost] = useState<HTMLElement | null>(null)
  const [panel, setPanel] = useState<Panel>(null)

  useEffect(() => setHost(document.body), [])

  useEffect(() => {
    if (!panel) return
    const escape = (e: KeyboardEvent) => e.key === 'Escape' && setPanel(null)
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [panel])

  const toggle = (next: Exclude<Panel, null>) => setPanel((p) => (p === next ? null : next))

  if (!host) return null

  const groups = GROUPS.map((ids) => ids.map((id) => tools[id]).filter(Boolean)).filter(
    (group) => group.length > 0,
  )
  // Everything the strip doesn't show — the shape variants, highlighter, laser and so on.
  // The default toolbar hid these behind its own overflow; dropping them would trade a
  // layout change for a capability loss.
  const shown = new Set(GROUPS.flat())
  const rest = Object.values(tools).filter((t) => !shown.has(t.id))

  return createPortal(
    <div className="tool-rail" role="toolbar" aria-label="Tools" aria-orientation="vertical">
      {groups.map((group, i) => (
        <div className="tool-group" key={group[0].id}>
          {i > 0 && <span className="tool-sep" aria-hidden="true" />}
          {group.map((tool) => (
            <ToolButton key={tool.id} tool={tool} />
          ))}
        </div>
      ))}

      {rest.length > 0 && (
        <>
          <span className="tool-sep" aria-hidden="true" />
          <TldrawUiButton
            type="tool"
            isActive={panel === 'more'}
            title="More tools"
            aria-label="More tools"
            aria-expanded={panel === 'more'}
            onClick={() => toggle('more')}
          >
            <TldrawUiButtonIcon icon={panel === 'more' ? 'chevron-left' : 'chevron-right'} />
          </TldrawUiButton>
          {panel === 'more' && (
            <div className="tool-popover tool-popover--grid" role="group" aria-label="More tools">
              {rest.map((tool) => (
                <ToolButton key={tool.id} tool={tool} />
              ))}
            </div>
          )}
        </>
      )}

      <StylePanelToggle open={panel === 'style'} onToggle={() => toggle('style')} />
    </div>,
    host,
  )
}
