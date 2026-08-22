// Zone A: the one bar across the top of the canvas.
//
// It replaces tldraw's default menu cluster, which was six same-weight icons with the
// document's identity nowhere on it. The order is the order of the questions people ask:
// where am I (home), what is this (title), is it safe (save state) — then the controls
// that act on it, right-aligned so they never compete with the name.
//
// Mounted through tldraw's `TopPanel` slot, so `useEditor` works; everything it needs from
// outside the canvas comes through WorkspaceContext.

import { useEffect, useRef, useState } from 'react'
import { useEditor, useValue } from 'tldraw'
import { Home, Redo, SidebarRight, Undo } from '../ui/icons'
import { PageMenu } from './PageMenu'
import { ZoomMenu } from './ZoomMenu'
import { useWorkspace, type SaveState } from './workspace-context'

const SAVE_COPY: Record<SaveState, string> = {
  idle: '',
  unsaved: 'Unsaved changes',
  saving: 'Saving…',
  saved: 'Saved',
  error: "Couldn't save",
}

function SaveBadge({ state }: { state: SaveState }) {
  if (state === 'idle') return null
  return (
    // Announced politely: "is my work safe" is a question worth answering for a screen
    // reader too, but not one worth interrupting anything for.
    <span
      className={`save save--${state}`}
      role="status"
      aria-live="polite"
      // Narrow layouts collapse this to the dot alone; the title keeps the word reachable
      // so the state is never carried by colour by itself.
      title={SAVE_COPY[state]}
    >
      <span className="save-dot" aria-hidden="true" />
      {SAVE_COPY[state]}
    </span>
  )
}

export function WorkspaceHeader() {
  const editor = useEditor()
  const { title, onRename, saveState, onHome, railOpen, onToggleRail, busy } = useWorkspace()
  const [editing, setEditing] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  const canUndo = useValue('can undo', () => editor.getCanUndo(), [editor])
  const canRedo = useValue('can redo', () => editor.getCanRedo(), [editor])

  useEffect(() => {
    if (editing) input.current?.select()
  }, [editing])

  const commit = () => {
    const next = input.current?.value.trim()
    setEditing(false)
    if (next && next !== title) onRename(next)
  }

  return (
    <header className="wshead">
      <div className="wshead-left">
        <button className="icon-btn" onClick={onHome} title="All diagrams" aria-label="All diagrams">
          <Home size={16} />
        </button>

        <span className="wshead-div" aria-hidden="true" />

        {editing ? (
          <input
            ref={input}
            className="wshead-rename"
            defaultValue={title}
            aria-label="Diagram name"
            onKeyDown={(e) => {
              // Stopped here, or tldraw's canvas shortcuts fire while you type a name.
              e.stopPropagation()
              if (e.key === 'Enter') commit()
              if (e.key === 'Escape') setEditing(false)
            }}
            onBlur={commit}
          />
        ) : (
          <button
            className="wshead-title"
            onClick={() => !busy && setEditing(true)}
            title={busy ? 'Renaming is available once the run finishes' : 'Rename'}
            disabled={busy}
          >
            {title || 'Untitled'}
          </button>
        )}

        <SaveBadge state={saveState} />
      </div>

      <div className="wshead-right">
        <PageMenu />

        <span className="wshead-div" aria-hidden="true" />

        <button
          className="icon-btn"
          onClick={() => editor.undo()}
          disabled={!canUndo}
          title="Undo — ⌘Z"
          aria-label="Undo"
        >
          <Undo size={16} />
        </button>
        <button
          className="icon-btn"
          onClick={() => editor.redo()}
          disabled={!canRedo}
          title="Redo — ⇧⌘Z"
          aria-label="Redo"
        >
          <Redo size={16} />
        </button>

        <span className="wshead-div" aria-hidden="true" />

        <ZoomMenu />

        {/* The rail's own collapse control disappears with the rail, so the control that
            brings it back has to live out here. One button, one place, both directions. */}
        <button
          className={`icon-btn${railOpen ? '' : ' is-on'}`}
          onClick={onToggleRail}
          title={railOpen ? 'Hide Canvo AI' : 'Show Canvo AI'}
          aria-label={railOpen ? 'Hide Canvo AI' : 'Show Canvo AI'}
          aria-pressed={!railOpen}
        >
          <SidebarRight size={16} />
        </button>
      </div>
    </header>
  )
}
