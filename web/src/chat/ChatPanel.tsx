// The rail: everything the product says lives here, so the canvas keeps the whole screen.
// Header (identity + history), the run log, and the composer.

import { useEffect, useRef, useState } from 'react'
import type { ChatMessage, Conversation, RunActivity } from '../lib/conversations'
import { AgentTurn } from './AgentTurn'
import { Composer } from './Composer'
import { HistoryMenu } from './HistoryMenu'

const SAMPLES: { label: string; text: string }[] = [
  {
    label: 'JWT workflow',
    text: `Draw a JWT authentication workflow: the user submits login credentials from the client app, the auth service validates them against the user database, on success it issues an access token and a refresh token, the client stores the tokens and calls the API gateway with the access token, the gateway verifies the token signature and forwards valid requests to backend services, expired tokens go through the refresh flow to get a new access token, and invalid tokens return an unauthorized error to the client.`,
  },
  {
    label: 'SQL schema',
    text: `CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  created_at TIMESTAMP
);

CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  total NUMERIC(10,2) NOT NULL,
  status VARCHAR(32)
);`,
  },
  {
    label: 'Order pipeline',
    text: 'Show how an order flows through a checkout system end to end, including payment failure and refund paths.',
  },
]

export function ChatPanel({
  title,
  messages,
  live,
  liveStatus,
  busy,
  draft,
  onDraft,
  onSend,
  conversations,
  activeId,
  onNew,
  onSelect,
  onDelete,
  onCollapse,
  onFocusDiagram,
}: {
  title: string
  messages: ChatMessage[]
  live: RunActivity | null
  liveStatus: string
  busy: boolean
  draft: string
  onDraft: (v: string) => void
  onSend: () => void
  conversations: Conversation[]
  activeId: string | null
  onNew: () => void
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onCollapse: () => void
  onFocusDiagram: () => void
}) {
  const [historyOpen, setHistoryOpen] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const empty = messages.length === 0 && !live

  // Follow the run as it streams; the newest step is the one worth reading.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, live, liveStatus])

  return (
    <aside className="rail">
      <header className="rail-head">
        <h1 className="rail-title" title={title}>
          {empty ? 'New diagram' : title}
        </h1>
        <div className="rail-actions">
          <button className="head-btn" onClick={onNew} title="New diagram" aria-label="New diagram">
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
          <div className="menu-anchor">
            <button
              className="head-btn"
              onClick={() => setHistoryOpen((v) => !v)}
              title="History"
              aria-label="History"
              aria-expanded={historyOpen}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                <path
                  d="M8 4.5V8l2.5 1.5M8 2.5a5.5 5.5 0 1 1-5.5 5.5"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  fill="none"
                />
              </svg>
            </button>
            {historyOpen && (
              <HistoryMenu
                conversations={conversations}
                activeId={activeId}
                onSelect={(id) => {
                  setHistoryOpen(false)
                  onSelect(id)
                }}
                onDelete={onDelete}
                onClose={() => setHistoryOpen(false)}
              />
            )}
          </div>
          <button
            className="head-btn"
            onClick={onCollapse}
            title="Hide panel"
            aria-label="Hide panel"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path
                d="M6 4l4 4-4 4"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
              />
            </svg>
          </button>
        </div>
      </header>

      <div className="log">
        {empty && (
          <div className="welcome">
            <p>
              Describe a system in plain words. Canvo writes a spec first — including the
              assumptions it had to make — then draws it and reviews its own layout.
            </p>
            <div className="samples">
              {SAMPLES.map((s) => (
                <button key={s.label} className="chip" onClick={() => onDraft(s.text)}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) =>
          m.role === 'user' ? (
            <div key={m.id} className="turn turn--user">
              <p>{m.text}</p>
            </div>
          ) : m.activity ? (
            <AgentTurn key={m.id} activity={m.activity} onFocus={onFocusDiagram} />
          ) : (
            <div key={m.id} className="turn turn--agent">
              <p className="turn-result">{m.text}</p>
            </div>
          ),
        )}

        {live && <AgentTurn activity={live} live liveStatus={liveStatus} />}
        <div ref={endRef} />
      </div>

      <Composer
        value={draft}
        onChange={onDraft}
        onSend={onSend}
        busy={busy}
        samples={SAMPLES}
      />
    </aside>
  )
}
