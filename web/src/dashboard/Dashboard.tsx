// Where a session starts: pick up a diagram or begin one.
//
// The openers are the service's actual input routes — prose, SQL, an OpenAPI document, or
// a blank canvas. That is deliberate: a row of cards for capabilities the product doesn't
// have is a worse first impression than four that all work.

import { useCallback, useEffect, useMemo, useState } from 'react'
import { logout, type Account } from '../lib/auth'
import {
  createConversation,
  deleteConversation,
  listConversations,
  relativeTime,
  type Conversation,
} from '../lib/conversations'
import { OPENERS } from './openers'

export default function Dashboard({
  onNavigate,
  account,
  onSignedOut,
}: {
  onNavigate: (to: string) => void
  account: Account
  onSignedOut: () => void
}) {
  const [items, setItems] = useState<Conversation[]>([])
  const [query, setQuery] = useState('')
  const [loaded, setLoaded] = useState(false)
  const [offline, setOffline] = useState(false)

  const load = useCallback(async () => {
    try {
      setItems(await listConversations())
      setOffline(false)
    } catch {
      setOffline(true)
    } finally {
      setLoaded(true)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const open = useCallback(
    async (start?: string) => {
      const created = await createConversation()
      onNavigate(`/d/${created.id}${start ? `?start=${start}` : ''}`)
    },
    [onNavigate],
  )

  const remove = useCallback(
    async (id: string) => {
      setItems((prev) => prev.filter((c) => c.id !== id))
      await deleteConversation(id)
      void load()
    },
    [load],
  )

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? items.filter((c) => c.title.toLowerCase().includes(q)) : items
  }, [items, query])

  return (
    <div className="dash">
      <aside className="dash-side">
        <div className="dash-brand">
          <span className="dash-mark" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 20 20">
              <path
                d="M3 3.5v13h13M7 12.5V8M11 12.5V4.5M15 12.5v-3"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
              />
            </svg>
          </span>
          <span className="dash-wordmark">Canvo</span>
        </div>

        <nav className="dash-nav">
          <span className="dash-nav-item is-active">All diagrams</span>
        </nav>

        <div className="dash-note">
          <p className="dash-note-title">Every diagram keeps its chat</p>
          <p>
            Canvo writes a spec before it draws — the assumptions it made are saved with the
            diagram, so you can reopen one and see how it got there.
          </p>
        </div>

        <div className="dash-foot">
          <button className="dash-new" onClick={() => void open('ai')}>
            New diagram
          </button>
          <div className="dash-account">
            <span className="dash-email" title={account.email}>
              {account.email}
            </span>
            <button
              className="dash-signout"
              onClick={() => void logout().then(onSignedOut)}
            >
              Sign out
            </button>
          </div>
        </div>
      </aside>

      <main className="dash-main">
        <header className="dash-head">
          <h1>Your diagrams</h1>
          <div className="dash-search">
            <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
              <circle cx="7" cy="7" r="4.25" stroke="currentColor" strokeWidth="1.4" fill="none" />
              <path d="M10.2 10.2L13.5 13.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search diagrams"
              aria-label="Search diagrams"
            />
          </div>
        </header>

        <section className="openers" aria-label="Start a diagram">
          {OPENERS.map((o) => (
            <button key={o.id} className="opener" onClick={() => void open(o.id)}>
              <span className="opener-icon" aria-hidden="true">
                {o.icon}
              </span>
              <span className="opener-title">{o.title}</span>
              <span className="opener-sub">{o.sub}</span>
            </button>
          ))}
        </section>

        <section className="listing">
          <div className="listing-head" role="row">
            <span>Name</span>
            <span>Turns</span>
            <span>Created</span>
            <span>Edited</span>
            <span />
          </div>

          {!loaded && <p className="listing-empty">Loading…</p>}

          {loaded && offline && (
            <p className="listing-empty listing-empty--error">
              Can't reach the agent on :8000. Start it and reload.
            </p>
          )}

          {loaded && !offline && shown.length === 0 && (
            <p className="listing-empty">
              {items.length
                ? `Nothing matches “${query}”.`
                : 'No diagrams yet — start one above.'}
            </p>
          )}

          {shown.map((c) => (
            <div key={c.id} className="listing-row">
              <button className="listing-open" onClick={() => onNavigate(`/d/${c.id}`)}>
                <span className="listing-name">{c.title}</span>
                {/* A conversation with no canvas was started and never drawn — worth
                    saying so, since the row otherwise looks like finished work. */}
                {!c.has_canvas && <span className="listing-tag">empty</span>}
              </button>
              <span className="listing-cell">{c.messages || '—'}</span>
              <span className="listing-cell">{relativeTime(c.created_at)}</span>
              <span className="listing-cell">{relativeTime(c.updated_at)}</span>
              <button
                className="listing-delete"
                onClick={() => void remove(c.id)}
                aria-label={`Delete ${c.title}`}
                title="Delete"
              >
                <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
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
            </div>
          ))}
        </section>
      </main>
    </div>
  )
}
