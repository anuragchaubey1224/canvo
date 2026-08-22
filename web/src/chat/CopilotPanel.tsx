// Zone C: the copilot.
//
// Not a chat window that happens to sit next to a canvas. The diagram is the artefact;
// this panel is the instrument that makes and changes it, so the turns are records of
// work rather than a transcript, and what the panel offers changes with the state of the
// canvas — cold start, diagram present, something selected.

import { useEffect, useRef, useState } from 'react'
import type { ChatMessage, Conversation, RunActivity } from '../lib/conversations'
import { History, Sparkle } from '../ui/icons'
import { AgentTurn } from './AgentTurn'
import { Composer } from './Composer'
import { HistoryMenu } from './HistoryMenu'
import { forSelection, REFINEMENTS, STARTERS } from './suggestions'

export function CopilotPanel({
  title,
  messages,
  live,
  liveStatus,
  busy,
  draft,
  onDraft,
  onSend,
  onRetry,
  conversations,
  activeId,
  onSelect,
  onDelete,
  onCollapse,
  onFocusDiagram,
  hasDiagram,
  selection,
  runsLeft,
}: {
  title: string
  messages: ChatMessage[]
  live: RunActivity | null
  liveStatus: string
  busy: boolean
  draft: string
  onDraft: (v: string) => void
  onSend: () => void
  onRetry: () => void
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onCollapse: () => void
  onFocusDiagram: () => void
  hasDiagram: boolean
  selection: string[]
  runsLeft: number | null
}) {
  const [historyOpen, setHistoryOpen] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const cold = messages.length === 0 && !live

  // Follow the run as it streams; the newest step is the one worth reading.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, live, liveStatus])

  const lastFailed =
    messages.length > 0 &&
    messages[messages.length - 1].role === 'assistant' &&
    Boolean(messages[messages.length - 1].activity?.error)

  // What to offer beneath the last turn: whatever is selected wins, because that is the
  // most specific thing the user has told us they care about.
  const suggestions = selection.length ? forSelection(selection) : REFINEMENTS

  return (
    <aside className="rail" aria-label="Canvo AI">
      <header className="rail-head">
        <span className="rail-mark" aria-hidden="true">
          <Sparkle size={15} />
        </span>
        <span className="rail-identity">
          <span className="rail-name">Canvo AI</span>
          <span className="rail-role">{busy ? 'Working…' : 'Diagram copilot'}</span>
        </span>

        <div className="rail-actions">
          <div className="menu-anchor">
            <button
              className="icon-btn"
              onClick={() => setHistoryOpen((v) => !v)}
              title="Recent diagrams"
              aria-label="Recent diagrams"
              aria-expanded={historyOpen}
              aria-haspopup="menu"
            >
              <History size={16} />
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
            className="icon-btn"
            onClick={onCollapse}
            title="Hide Canvo AI"
            aria-label="Hide Canvo AI"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path
                d="M6 4l4 4-4 4"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
              />
            </svg>
          </button>
        </div>
      </header>

      <div className="log">
        {cold && (
          <div className="onboard">
            <h2 className="onboard-title">Describe what you want to visualise</h2>
            <p className="onboard-body">
              Canvo writes a specification first — including the assumptions it had to make
              — then draws the diagram and reviews its own layout. Follow-up messages edit
              the diagram rather than starting over.
            </p>
            <p className="onboard-label">Try one of these</p>
            <div className="chips chips--stack">
              {STARTERS.map((s) => (
                <button
                  key={s.label}
                  className="chip"
                  onClick={() => onDraft(s.text)}
                  title="Put this in the composer"
                >
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
            <AgentTurn
              key={m.id}
              activity={m.activity}
              fallbackTitle={title}
              onFocus={onFocusDiagram}
              onRetry={lastFailed && m.id === messages[messages.length - 1].id ? onRetry : undefined}
            />
          ) : (
            <div key={m.id} className="turn turn--agent">
              <p className="turn-result">{m.text}</p>
            </div>
          ),
        )}

        {live && <AgentTurn activity={live} live liveStatus={liveStatus} fallbackTitle={title} />}

        {/* Next moves, once there is something to move on. Four at most: a wall of chips
            is a menu nobody reads. */}
        {!cold && !busy && hasDiagram && !lastFailed && runsLeft !== 0 && (
          <div className="followups">
            <p className="followups-label">
              {selection.length ? 'For the selection' : 'Refine this diagram'}
            </p>
            <div className="chips">
              {suggestions.map((s) => (
                <button key={s.label} className="chip" onClick={() => onDraft(s.text)}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      {/* The run's state, for a screen reader. Visually it is already on the turn above. */}
      <p className="sr-only" role="status" aria-live="polite">
        {busy ? liveStatus || 'Generating the diagram' : ''}
      </p>

      <Composer
        value={draft}
        onChange={onDraft}
        onSend={onSend}
        busy={busy}
        hasDiagram={hasDiagram}
        selection={selection}
        runsLeft={runsLeft}
      />
    </aside>
  )
}
