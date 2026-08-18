// Conversation switcher. The canvas owns the screen, so history lives in a popover off
// the rail header rather than a third column competing with the diagram for space.

import { useEffect, useRef } from 'react'
import { relativeTime, type Conversation } from '../lib/conversations'

export function HistoryMenu({
  conversations,
  activeId,
  onSelect,
  onDelete,
  onClose,
}: {
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onClose: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const away = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) onClose()
    }
    const escape = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    // Deferred: the click that opened the menu is still propagating.
    const t = window.setTimeout(() => document.addEventListener('mousedown', away))
    document.addEventListener('keydown', escape)
    return () => {
      window.clearTimeout(t)
      document.removeEventListener('mousedown', away)
      document.removeEventListener('keydown', escape)
    }
  }, [onClose])

  return (
    <div className="history" ref={ref} role="menu">
      <p className="history-head">Recent diagrams</p>
      {conversations.length === 0 && <p className="history-empty">Nothing saved yet.</p>}
      <ul className="history-list">
        {conversations.map((c) => (
          <li key={c.id} className="history-item" data-active={c.id === activeId}>
            <button className="history-open" onClick={() => onSelect(c.id)} role="menuitem">
              <span className="history-title">{c.title}</span>
              <span className="history-meta">
                {relativeTime(c.updated_at)}
                {c.messages > 0 && ` · ${c.messages} turn${c.messages > 1 ? 's' : ''}`}
              </span>
            </button>
            <button
              className="history-delete"
              onClick={() => onDelete(c.id)}
              aria-label={`Delete ${c.title}`}
              title="Delete"
            >
              <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true">
                <path
                  d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.6 8h5.8l.6-8"
                  stroke="currentColor"
                  strokeWidth="1.3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  fill="none"
                />
              </svg>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
