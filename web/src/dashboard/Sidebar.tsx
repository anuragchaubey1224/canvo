// Product navigation.
//
// Three views over one list, not three pages: "Drafts" exists because a diagram that was
// started and never drawn is genuinely different work, and burying those among finished
// diagrams is what made the old listing read as clutter. Counts are on every item so the
// filter is a decision the user can make before clicking it.

import { useEffect } from 'react'
import type { Account } from '../lib/auth'
import { Clock, Draft, Layers, Logo, Logout, PanelLeft, Plus, Shield } from '../ui/icons'
import Menu from '../ui/Menu'

export type View = 'all' | 'recent' | 'drafts'

const VIEWS: { id: View; label: string; icon: typeof Layers }[] = [
  { id: 'all', label: 'All diagrams', icon: Layers },
  { id: 'recent', label: 'Recent', icon: Clock },
  { id: 'drafts', label: 'Drafts', icon: Draft },
]

export default function Sidebar({
  view,
  counts,
  collapsed,
  drawerOpen,
  account,
  onView,
  onHome,
  onToggleCollapsed,
  onCloseDrawer,
  onNew,
  onSignOut,
  onVerify,
}: {
  view: View
  counts: Record<View, number>
  collapsed: boolean
  drawerOpen: boolean
  account: Account
  onView: (v: View) => void
  onHome: () => void
  onToggleCollapsed: () => void
  onCloseDrawer: () => void
  onNew: () => void
  onSignOut: () => void
  onVerify: () => void
}) {
  // The drawer is a modal surface on small screens: Esc has to close it, or the only way
  // out is a tap on a scrim that a keyboard user cannot reach.
  useEffect(() => {
    if (!drawerOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onCloseDrawer()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [drawerOpen, onCloseDrawer])

  return (
    <aside
      className={`side${collapsed ? ' is-collapsed' : ''}${drawerOpen ? ' is-open' : ''}`}
      aria-label="Canvo"
    >
      <div className="side-top">
        <a
          className="side-brand"
          href="/dashboard"
          aria-label="Canvo — dashboard"
          onClick={(e) => {
            e.preventDefault()
            onHome()
          }}
        >
          <span className="brand-mark" aria-hidden="true">
            <Logo size={17} />
          </span>
          <span className="brand-wordmark">Canvo</span>
        </a>
        <button
          className="side-collapse"
          onClick={onToggleCollapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <PanelLeft size={16} />
        </button>
      </div>

      {/* The product's one persistent action, in the one place it is always reachable —
          the page header's copy scrolls away, this one does not. */}
      <button className="side-new" onClick={onNew}>
        <Plus size={16} />
        <span className="side-new-label">New diagram</span>
      </button>

      <nav className="side-nav" aria-label="Diagram views">
        {VIEWS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`side-item${view === id ? ' is-active' : ''}`}
            aria-current={view === id ? 'page' : undefined}
            onClick={() => onView(id)}
            title={collapsed ? label : undefined}
          >
            <span className="side-item-icon" aria-hidden="true">
              <Icon size={16} />
            </span>
            <span className="side-item-label">{label}</span>
            <span className="side-count">{counts[id]}</span>
          </button>
        ))}
      </nav>

      <div className="side-fill" />

      {/* Not a blocker — an unverified account works fine. It matters the day someone
          needs to recover it, which is exactly the day it is too late to confirm. Here it
          is a quiet, permanent affordance; the banner above the list is the prompt. */}
      {!account.email_verified && !collapsed && (
        <button className="side-verify" onClick={onVerify}>
          <Shield size={15} />
          <span>
            <strong>Confirm your email</strong>
            <span>Enables account recovery</span>
          </span>
        </button>
      )}

      <Menu
        className="side-account"
        label={`Account: ${account.email}`}
        trigger={
          <>
            <span className="side-avatar" aria-hidden="true">
              {account.email.slice(0, 1).toUpperCase()}
            </span>
            <span className="side-identity">
              <span className="side-email">{account.email}</span>
              <span className="side-plan">
                {account.email_verified ? 'Verified' : 'Unverified email'}
              </span>
            </span>
          </>
        }
        items={[{ label: 'Sign out', icon: <Logout size={15} />, onSelect: onSignOut }]}
      />
    </aside>
  )
}
