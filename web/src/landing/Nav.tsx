// The marketing nav.
//
// Two states, decided by whether anyone is signed in: a visitor is offered a way in, and
// someone who already has an account is offered the way back to their work. Showing
// "Sign up" to a signed-in user is the small tell that a site does not know who you are.

import { useEffect, useState } from 'react'
import type { Account } from '../lib/auth'
import { Logo } from '../ui/icons'

const LINKS = [
  { href: '#how', label: 'How it works' },
  { href: '#product', label: 'Product' },
  { href: '#uses', label: 'Use cases' },
  { href: '#faq', label: 'FAQ' },
]

export function Nav({
  account,
  onNavigate,
}: {
  account: Account | null
  onNavigate: (to: string) => void
}) {
  const [lifted, setLifted] = useState(false)
  const [open, setOpen] = useState(false)

  // The bar earns its border once the page has moved under it, and not before — a
  // permanent divider on a hero is a line for the sake of a line.
  useEffect(() => {
    const onScroll = () => setLifted(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const go = (to: string) => (e: React.MouseEvent) => {
    e.preventDefault()
    setOpen(false)
    onNavigate(to)
  }

  return (
    <header className={`nav${lifted ? ' is-lifted' : ''}`}>
      <div className="nav-inner">
        <a className="nav-brand" href="/" onClick={go('/')}>
          <span className="brand-mark" aria-hidden="true">
            <Logo size={17} />
          </span>
          <span className="brand-wordmark">Canvo</span>
        </a>

        <nav className={`nav-links${open ? ' is-open' : ''}`} aria-label="Sections">
          {LINKS.map((l) => (
            <a key={l.href} href={l.href} onClick={() => setOpen(false)}>
              {l.label}
            </a>
          ))}
        </nav>

        <div className="nav-actions">
          {account ? (
            <>
              <span className="nav-who" title={account.email}>
                {account.email}
              </span>
              <a className="btn btn--primary" href="/dashboard" onClick={go('/dashboard')}>
                Open Canvo
              </a>
            </>
          ) : (
            <>
              <a className="nav-link" href="/login" onClick={go('/login')}>
                Log in
              </a>
              <a className="btn btn--primary" href="/signup" onClick={go('/signup')}>
                Get started
              </a>
            </>
          )}
        </div>

        <button
          className="nav-burger"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={open ? 'Close menu' : 'Open menu'}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
            <path
              d={open ? 'M6 6l12 12M18 6L6 18' : 'M4 8h16M4 16h16'}
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              fill="none"
            />
          </svg>
        </button>
      </div>
    </header>
  )
}
