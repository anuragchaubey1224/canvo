// Where a session starts: pick up a diagram or begin one.
//
// The screen answers, top to bottom, the questions someone has on arrival — what this is,
// how to start, and what I already have. The four openers are the service's actual input
// routes, so the creation area is a real menu rather than a single button that drops you
// somewhere you have to work out.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { logout, resendVerification, runsLeft, type Account } from '../lib/auth'
import {
  createConversation,
  deleteConversation,
  listConversations,
  renameConversation,
  type Conversation,
} from '../lib/conversations'
import ConfirmDialog from '../ui/ConfirmDialog'
import { ToastHost } from '../ui/Toast'
import { useToast } from '../ui/toast-context'
import { PanelLeft, Search, Shield, X } from '../ui/icons'
import DiagramList from './DiagramList'
import Sidebar, { type View } from './Sidebar'
import { OPENERS } from './openers'

type Sort = 'edited' | 'created' | 'name'

const SORTS: { id: Sort; label: string }[] = [
  { id: 'edited', label: 'Last edited' },
  { id: 'created', label: 'Recently created' },
  { id: 'name', label: 'Name (A–Z)' },
]

const RECENT_MS = 7 * 24 * 60 * 60 * 1000
const COLLAPSE_KEY = 'canvo:sidebar-collapsed'
const NAG_KEY = 'canvo:verify-dismissed'

export default function Dashboard(props: {
  onNavigate: (to: string) => void
  account: Account
  onSignedOut: () => void
}) {
  // The toast host has to sit above anything that reports, so the dashboard body is a
  // child of it rather than a sibling.
  return (
    <ToastHost>
      <DashboardBody {...props} />
    </ToastHost>
  )
}

function DashboardBody({
  onNavigate,
  account,
  onSignedOut,
}: {
  onNavigate: (to: string) => void
  account: Account
  onSignedOut: () => void
}) {
  const toast = useToast()
  const left = runsLeft(account)
  const [items, setItems] = useState<Conversation[]>([])
  const [query, setQuery] = useState('')
  const [view, setView] = useState<View>('all')
  const [sort, setSort] = useState<Sort>('edited')
  const [loaded, setLoaded] = useState(false)
  // When the list was fetched. "Recent" is measured from here rather than from the clock
  // at render time, so the window doesn't drift between renders of the same data.
  const [loadedAt, setLoadedAt] = useState(0)
  const [offline, setOffline] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<Conversation | null>(null)
  const [creating, setCreating] = useState(false)
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(COLLAPSE_KEY) === '1',
  )
  const [drawerOpen, setDrawerOpen] = useState(false)
  // Dismissal is per browsing session, not permanent: an unverified account is a standing
  // risk, so the prompt should come back — just not on every navigation within one sitting.
  const [nagDismissed, setNagDismissed] = useState(
    () => sessionStorage.getItem(NAG_KEY) === '1',
  )
  const [verifySent, setVerifySent] = useState(false)
  const search = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    try {
      setItems(await listConversations())
      setLoadedAt(Date.now())
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

  useEffect(() => {
    localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0')
  }, [collapsed])

  // ⌘K / Ctrl-K focuses search. Earned rather than decorative: this list grows without
  // bound and reaching the field is otherwise a scroll plus a click.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        search.current?.focus()
        search.current?.select()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const open = useCallback(
    async (start?: string) => {
      if (creating) return // a double-click must not leave two empty diagrams behind
      setCreating(true)
      try {
        const created = await createConversation()
        onNavigate(`/d/${created.id}${start ? `?start=${start}` : ''}`)
      } catch {
        toast("Couldn't start a diagram — is the agent running?", 'error')
        setCreating(false)
      }
    },
    [creating, onNavigate, toast],
  )

  const rename = useCallback(
    async (id: string, title: string) => {
      const previous = items
      setItems((prev) => prev.map((c) => (c.id === id ? { ...c, title } : c)))
      try {
        await renameConversation(id, title)
        toast('Diagram renamed', 'success')
      } catch {
        setItems(previous)
        toast("Couldn't rename that diagram", 'error')
      }
    },
    [items, toast],
  )

  const confirmDelete = useCallback(async () => {
    const target = pendingDelete
    if (!target) return
    setPendingDelete(null)
    const previous = items
    setItems((prev) => prev.filter((c) => c.id !== target.id))
    try {
      await deleteConversation(target.id)
      toast(`Deleted “${target.title || 'Untitled'}”`, 'success')
    } catch {
      // Optimistic removal has to be reversible, or a failed request silently loses a
      // diagram from the list until the next reload.
      setItems(previous)
      toast("Couldn't delete that diagram", 'error')
    }
  }, [items, pendingDelete, toast])

  const sendVerification = useCallback(async () => {
    setVerifySent(true)
    try {
      await resendVerification()
      toast(`Verification link sent to ${account.email}`, 'success')
    } catch {
      // The server answers the same way whether or not it sent one; a failure here is a
      // transport problem, and re-arming the button is the useful response.
      setVerifySent(false)
      toast("Couldn't send the link just now", 'error')
    }
  }, [account.email, toast])

  const counts = useMemo(
    () => ({
      all: items.length,
      recent: items.filter((c) => loadedAt - new Date(c.updated_at).getTime() < RECENT_MS)
        .length,
      drafts: items.filter((c) => !c.has_canvas).length,
    }),
    [items, loadedAt],
  )

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    const filtered = items.filter((c) => {
      if (view === 'drafts' && c.has_canvas) return false
      if (view === 'recent' && loadedAt - new Date(c.updated_at).getTime() >= RECENT_MS)
        return false
      return q ? c.title.toLowerCase().includes(q) : true
    })
    const by = {
      edited: (a: Conversation, b: Conversation) => b.updated_at.localeCompare(a.updated_at),
      created: (a: Conversation, b: Conversation) => b.created_at.localeCompare(a.created_at),
      name: (a: Conversation, b: Conversation) =>
        (a.title || 'Untitled').localeCompare(b.title || 'Untitled'),
    }[sort]
    return [...filtered].sort(by)
  }, [items, loadedAt, query, sort, view])

  const searching = query.trim().length > 0
  const emptyState = searching
    ? {
        title: `No diagrams match “${query.trim()}”`,
        body: 'Try a shorter phrase, or clear the search to see everything.',
        action: { label: 'Clear search', onClick: () => setQuery('') },
      }
    : view === 'drafts'
      ? {
          title: 'No drafts',
          body: 'Diagrams you start but never draw show up here.',
        }
      : view === 'recent'
        ? {
            title: 'Nothing edited this week',
            body: 'Diagrams you touch in the last seven days appear here.',
            action: { label: 'View all diagrams', onClick: () => setView('all') },
          }
        : {
            title: 'No diagrams yet',
            body: 'Describe a system in plain words, paste a SQL schema or an OpenAPI spec, or start from a blank canvas.',
            action: { label: 'Generate your first diagram', onClick: () => void open('ai') },
          }

  const showNag = !account.email_verified && !nagDismissed

  return (
    <div className={`dash${collapsed ? ' is-collapsed' : ''}`}>
      <Sidebar
        view={view}
        counts={counts}
        collapsed={collapsed}
        drawerOpen={drawerOpen}
        account={account}
        onView={(v) => {
          setView(v)
          setDrawerOpen(false)
        }}
        onHome={() => {
          setView('all')
          setQuery('')
          setDrawerOpen(false)
        }}
        onToggleCollapsed={() => setCollapsed((c) => !c)}
        onCloseDrawer={() => setDrawerOpen(false)}
        onNew={() => void open('ai')}
        onSignOut={() => void logout().then(onSignedOut)}
        onVerify={() => void sendVerification()}
      />

      {/* Only reachable below the drawer breakpoint, where the sidebar is an overlay. */}
      {drawerOpen && (
        <button className="side-scrim" aria-label="Close navigation" onClick={() => setDrawerOpen(false)} />
      )}

      <main className="main">
        <div className="topbar">
          <button
            className="topbar-menu"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open navigation"
            aria-expanded={drawerOpen}
          >
            <PanelLeft size={17} />
          </button>
          <span className="topbar-title">Canvo</span>
        </div>

        <div className="main-inner">
          {showNag && (
            <div className="notice" role="status">
              <span className="notice-icon" aria-hidden="true">
                <Shield size={16} />
              </span>
              <span className="notice-copy">
                <strong>Secure your account</strong>
                <span>
                  Confirm <b>{account.email}</b> so you can recover it by email if you ever
                  lose your password.
                </span>
              </span>
              <button
                className="btn btn--quiet"
                onClick={() => void sendVerification()}
                disabled={verifySent}
              >
                {verifySent ? 'Link sent' : 'Send confirmation'}
              </button>
              <button
                className="notice-dismiss"
                aria-label="Dismiss for now"
                onClick={() => {
                  sessionStorage.setItem(NAG_KEY, '1')
                  setNagDismissed(true)
                }}
              >
                <X size={14} />
              </button>
            </div>
          )}

          <header className="head">
            <div className="head-copy">
              <h1>Your diagrams</h1>
              <p>
                Describe a system and Canvo writes the spec before it draws — every diagram
                keeps the conversation that produced it.
              </p>
            </div>
            <div className="head-side">
              {left !== null && (
                // Said before they start, not after they are refused.
                <p className={`allowance${left === 0 ? ' is-spent' : ''}`}>
                  {left === 0
                    ? 'No generations left'
                    : `${left} of ${account.runs_limit} generations left`}
                </p>
              )}
              <button className="btn btn--primary btn--lg" onClick={() => void open('ai')}>
                New diagram
              </button>
            </div>
          </header>

          <section className="openers" aria-label="Start a diagram">
            {OPENERS.map((o) => (
              <button
                key={o.id}
                className={`opener${o.featured ? ' opener--featured' : ''}`}
                onClick={() => void open(o.id)}
                disabled={creating}
              >
                <span className="opener-icon" aria-hidden="true">
                  {o.icon}
                </span>
                <span className="opener-title">{o.title}</span>
                <span className="opener-sub">{o.sub}</span>
              </button>
            ))}
          </section>

          <div className="toolbar">
            <div className="searchbox">
              <span className="searchbox-icon" aria-hidden="true">
                <Search size={15} />
              </span>
              <input
                ref={search}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Escape' && setQuery('')}
                placeholder="Search diagrams"
                aria-label="Search diagrams"
                type="search"
              />
              {searching ? (
                <button className="searchbox-clear" onClick={() => setQuery('')} aria-label="Clear search">
                  <X size={13} />
                </button>
              ) : (
                <kbd className="searchbox-kbd" aria-hidden="true">
                  ⌘K
                </kbd>
              )}
            </div>

            <div className="toolbar-right">
              {/* A count is the cheapest possible answer to "did my search do anything?" */}
              <span className="toolbar-count" aria-live="polite">
                {!loaded || offline
                  ? ' '
                  : shown.length === items.length
                    ? `${items.length} ${items.length === 1 ? 'diagram' : 'diagrams'}`
                    : `${shown.length} of ${items.length}`}
              </span>
              <label className="select">
                <span className="select-label">Sort</span>
                <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
                  {SORTS.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          <DiagramList
            items={shown}
            loading={!loaded}
            error={offline ? 'Agent unreachable' : null}
            empty={emptyState}
            onRetry={() => {
              setLoaded(false)
              void load()
            }}
            onOpen={(id) => onNavigate(`/d/${id}`)}
            onRename={(id, title) => void rename(id, title)}
            onDelete={setPendingDelete}
          />
        </div>
      </main>

      {pendingDelete && (
        <ConfirmDialog
          title="Delete this diagram?"
          body={`“${pendingDelete.title || 'Untitled'}” and the conversation that produced it will be removed. This can't be undone.`}
          confirmLabel="Delete"
          destructive
          onConfirm={() => void confirmDelete()}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </div>
  )
}
