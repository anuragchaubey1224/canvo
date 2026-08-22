// The list of diagrams.
//
// The name is the only thing a person scans for, so it is the only thing at full contrast;
// everything else — turn count, when it changed — is one muted line beneath it. The old
// table gave "Turns", "Created" and "Edited" three equal columns, which spent most of the
// row's width on numbers nobody chooses a diagram by.

import { useEffect, useRef, useState } from 'react'
import { agoLabel, type Conversation } from '../lib/conversations'
import Menu from '../ui/Menu'
import { Alert, ArrowUpRight, Board, Draft, More, Pencil, Trash } from '../ui/icons'

function exact(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function Row({
  item,
  onOpen,
  onRename,
  onDelete,
}: {
  item: Conversation
  onOpen: (id: string) => void
  onRename: (id: string, title: string) => void
  onDelete: (item: Conversation) => void
}) {
  const [editing, setEditing] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing) input.current?.select()
  }, [editing])

  const commit = () => {
    const next = input.current?.value.trim()
    setEditing(false)
    if (next && next !== item.title) onRename(item.id, next)
  }

  const turns = item.messages
    ? `${item.messages} ${item.messages === 1 ? 'turn' : 'turns'}`
    : 'Not started'

  return (
    <li className="row">
      <span className={`row-icon${item.has_canvas ? '' : ' row-icon--draft'}`} aria-hidden="true">
        {item.has_canvas ? <Board size={18} /> : <Draft size={17} />}
      </span>

      <span className="row-body">
        {editing ? (
          <input
            ref={input}
            className="row-rename"
            defaultValue={item.title}
            aria-label="Diagram name"
            onKeyDown={(e) => {
              if (e.key === 'Enter') commit()
              if (e.key === 'Escape') setEditing(false)
            }}
            onBlur={commit}
          />
        ) : (
          // Stretched by ::after over the whole row, so the click target is the row —
          // not just the ~200px of text. The actions sit above it on the z-axis.
          <button
            className="row-open"
            // The row's ::after covers the meta line, so a tooltip on those spans could
            // never be hovered. One here reaches the whole row.
            title={`Created ${exact(item.created_at)}\nEdited ${exact(item.updated_at)}`}
            onClick={() => onOpen(item.id)}
          >
            <span className="row-name">{item.title || 'Untitled'}</span>
          </button>
        )}
        <span className="row-meta">
          {!item.has_canvas && <span className="row-badge">Draft</span>}
          <span>{turns}</span>
          <span aria-hidden="true">·</span>
          <span>Edited {agoLabel(item.updated_at)}</span>
        </span>
      </span>

      <span className="row-actions">
        <Menu
          label={`Actions for ${item.title || 'Untitled'}`}
          trigger={<More size={16} />}
          items={[
            { label: 'Open', icon: <ArrowUpRight size={15} />, onSelect: () => onOpen(item.id) },
            { label: 'Rename', icon: <Pencil size={15} />, onSelect: () => setEditing(true) },
            {
              label: 'Delete',
              icon: <Trash size={15} />,
              destructive: true,
              onSelect: () => onDelete(item),
            },
          ]}
        />
      </span>
    </li>
  )
}

export default function DiagramList({
  items,
  loading,
  error,
  empty,
  onRetry,
  onOpen,
  onRename,
  onDelete,
}: {
  items: Conversation[]
  loading: boolean
  error: string | null
  onRetry: () => void
  /** What to say when there is nothing — depends on why, so the caller decides. */
  empty: { title: string; body: string; action?: { label: string; onClick: () => void } }
  onOpen: (id: string) => void
  onRename: (id: string, title: string) => void
  onDelete: (item: Conversation) => void
}) {
  if (loading) {
    return (
      <ul className="rows" aria-busy="true" aria-label="Loading diagrams">
        {[0, 1, 2, 3, 4].map((i) => (
          <li key={i} className="row row--skeleton">
            <span className="sk sk-icon" />
            <span className="row-body">
              {/* Uneven widths — equal bars read as a table, not as loading text. */}
              <span className="sk sk-line" style={{ width: `${52 - i * 6}%` }} />
              <span className="sk sk-line sk-line--meta" />
            </span>
          </li>
        ))}
      </ul>
    )
  }

  if (error) {
    return (
      <div className="state state--error" role="alert">
        <span className="state-icon state-icon--error" aria-hidden="true">
          <Alert size={22} />
        </span>
        <p className="state-title">{error}</p>
        <p className="state-body">
          Canvo can't reach the agent service on :8000. Start it, then try again.
        </p>
        <button className="btn btn--ghost" onClick={onRetry}>
          Try again
        </button>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="state">
        <span className="state-icon" aria-hidden="true">
          <Board size={22} />
        </span>
        <p className="state-title">{empty.title}</p>
        <p className="state-body">{empty.body}</p>
        {empty.action && (
          <button className="btn btn--primary" onClick={empty.action.onClick}>
            {empty.action.label}
          </button>
        )}
      </div>
    )
  }

  return (
    <ul className="rows">
      {items.map((item) => (
        <Row key={item.id} item={item} onOpen={onOpen} onRename={onRename} onDelete={onDelete} />
      ))}
    </ul>
  )
}
