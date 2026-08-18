// Zoom, as a percentage pill at the top-right of the canvas.
//
// tldraw's default puts zoom and a minimap in the bottom-left, permanently on screen. A
// pill that reads the current level and opens on demand costs nothing while you're
// reading a diagram, and puts the viewport controls next to the other canvas control
// rather than in a separate corner.
//
// Mounted through tldraw's `SharePanel` slot, which shares the top-right row with the
// style button — so the two canvas controls sit together.

import { useEffect, useRef, useState } from 'react'
import { useEditor, useValue } from 'tldraw'

const ROWS: { id: string; label: string; kbd: string; run: (e: ReturnType<typeof useEditor>) => void }[] = [
  { id: 'hand', label: 'Hand', kbd: 'Space', run: (e) => e.setCurrentTool('hand') },
  { id: 'fit', label: 'Zoom to fit', kbd: '⇧1', run: (e) => e.zoomToFit() },
  { id: 'selection', label: 'Zoom to selection', kbd: '⇧2', run: (e) => e.zoomToSelection() },
  { id: 'reset', label: 'Zoom to 100%', kbd: '⌘0', run: (e) => e.resetZoom() },
]

export function ZoomMenu() {
  const editor = useEditor()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const zoom = useValue('zoom', () => Math.round(editor.getZoomLevel() * 100), [editor])
  const hasSelection = useValue('selection', () => editor.getSelectedShapeIds().length > 0, [editor])

  useEffect(() => {
    if (!open) return
    const away = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    const escape = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    // Deferred: the pointer event that opened the menu is still propagating.
    const t = window.setTimeout(() => document.addEventListener('pointerdown', away))
    document.addEventListener('keydown', escape)
    return () => {
      window.clearTimeout(t)
      document.removeEventListener('pointerdown', away)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  return (
    <div className="zoom" ref={ref}>
      <button
        className="zoom-pill"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={`Zoom ${zoom}%`}
        title="Zoom"
      >
        <span className="zoom-value">{zoom}%</span>
        <svg width="10" height="10" viewBox="0 0 16 16" aria-hidden="true">
          <path
            d="M4 6.5L8 10.5l4-4"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </svg>
      </button>

      {open && (
        <div className="zoom-menu" role="menu">
          <div className="zoom-stepper">
            <button onClick={() => editor.zoomOut()} aria-label="Zoom out" title="Zoom out">
              <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M4 8h8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
            </button>
            <span className="zoom-stepper-value">{zoom}%</span>
            <button onClick={() => editor.zoomIn()} aria-label="Zoom in" title="Zoom in">
              <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
                <path
                  d="M8 4v8M4 8h8"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>

          {ROWS.map((row) => (
            <button
              key={row.id}
              className="zoom-row"
              role="menuitem"
              disabled={row.id === 'selection' && !hasSelection}
              onClick={() => {
                row.run(editor)
                setOpen(false)
              }}
            >
              <span>{row.label}</span>
              <kbd>{row.kbd}</kbd>
            </button>
          ))}

          <span className="zoom-sep" aria-hidden="true" />
          <button
            className="zoom-row"
            role="menuitem"
            onClick={() => {
              // tldraw's focus mode hides its own chrome; ours goes with it.
              editor.updateInstanceState({ isFocusMode: true })
              setOpen(false)
            }}
          >
            <span>Hide UI</span>
            <kbd>⌘\</kbd>
          </button>
        </div>
      )}
    </div>
  )
}
