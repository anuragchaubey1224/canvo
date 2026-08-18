// The tool strip: horizontal, along the bottom of the canvas.
//
// It sits in tldraw's own Toolbar slot rather than being positioned by hand, because that
// slot is already centred inside the canvas column — so the strip stays centred on the
// drawing whether the chat rail is open or collapsed, with no width arithmetic on our side.
// What we add is the grouping, the style button, and one flyout for everything else.

import { useEffect, useState } from 'react'
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

/** Which flyout is showing. One at a time — two panels above a 44px strip would collide. */
type Panel = 'more' | 'style' | null

export function Toolbar() {
  const tools = useTools()
  const [panel, setPanel] = useState<Panel>(null)

  useEffect(() => {
    if (!panel) return
    const escape = (e: KeyboardEvent) => e.key === 'Escape' && setPanel(null)
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [panel])

  const toggle = (next: Exclude<Panel, null>) => setPanel((p) => (p === next ? null : next))

  const groups = GROUPS.map((ids) => ids.map((id) => tools[id]).filter(Boolean)).filter(
    (group) => group.length > 0,
  )
  // Everything the strip doesn't show — the shape variants, highlighter, laser and so on.
  // The default toolbar hid these behind its own overflow; dropping them would trade a
  // layout change for a capability loss.
  const shown = new Set(GROUPS.flat())
  const rest = Object.values(tools).filter((t) => !shown.has(t.id))

  return (
    <div className="tool-bar" role="toolbar" aria-label="Tools">
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
            <TldrawUiButtonIcon icon={panel === 'more' ? 'chevron-down' : 'chevron-up'} />
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
    </div>
  )
}
