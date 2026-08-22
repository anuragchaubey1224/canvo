// Sign in, sign up, and the start of a password reset.
//
// One component, three modes, because the three share a form, a submit path and all of
// the error handling — and the two that matter share a URL each so they can be linked to
// from the marketing page and from an email.
//
// Server messages are shown as written. `/auth/signup` is worded never to reveal whether
// an address already has an account, and softening or reinterpreting it here would undo
// that. The only message this file writes itself is the one for a request that never
// arrived, which the server by definition cannot word.

import { useCallback, useEffect, useState } from 'react'
import {
  AuthError,
  login,
  OFFLINE_MESSAGE,
  requestReset,
  signup,
  type Account,
} from '../lib/auth'
import { Board, Check, Logo, Sparkle } from '../ui/icons'

type Mode = 'login' | 'signup' | 'forgot'

/** What the panel beside the form says. Product truth only — each line is something the
 *  service does today, and each is verifiable by using it. */
const PROOF: { icon: typeof Board; title: string; body: string }[] = [
  {
    icon: Sparkle,
    title: 'Describe it in plain words',
    body: 'Canvo writes a specification first — assumptions included — then draws it.',
  },
  {
    icon: Board,
    title: 'Edit by asking',
    body: 'Follow-up messages change the diagram you already have instead of starting over.',
  },
  {
    icon: Check,
    title: 'It reviews its own layout',
    body: 'Every diagram is checked for overlaps and crossed connections before you see it.',
  },
]

export default function AuthPage({
  mode: routeMode,
  onSignedIn,
  onNavigate,
  next,
}: {
  mode: 'login' | 'signup'
  onSignedIn: (account: Account) => void
  onNavigate: (to: string) => void
  next: string | null
}) {
  const [mode, setMode] = useState<Mode>(routeMode)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)

  // Following /login → /signup is a navigation, so the mode has to follow the URL as well
  // as the in-page toggle.
  useEffect(() => {
    setMode(routeMode)
    setError('')
    setSent(false)
  }, [routeMode])

  const submit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      if (busy) return
      setError('')

      if (mode === 'signup' && password !== confirm) {
        // Caught before the request: the server has no idea what the user meant to type
        // twice, and a round trip to be told so is a round trip wasted.
        setError("Those passwords don't match.")
        return
      }

      setBusy(true)
      try {
        if (mode === 'forgot') {
          await requestReset(email)
          // Shown whether or not that address has an account — the server deliberately
          // doesn't say, and echoing a difference here would give it away.
          setSent(true)
          setBusy(false)
          return
        }
        const account =
          mode === 'signup' ? await signup(email, password) : await login(email, password)
        onSignedIn(account)
      } catch (err) {
        setError(err instanceof AuthError ? err.message : OFFLINE_MESSAGE)
        setBusy(false)
      }
    },
    [busy, confirm, email, mode, onSignedIn, password],
  )

  const go = (to: Mode) => {
    if (to === 'forgot') {
      setMode('forgot')
      setError('')
      setSent(false)
      return
    }
    const query = next ? `?next=${encodeURIComponent(next)}` : ''
    onNavigate(`/${to}${query}`)
  }

  const title =
    mode === 'signup'
      ? 'Start building with Canvo'
      : mode === 'forgot'
        ? 'Reset your password'
        : 'Welcome back'
  const sub =
    mode === 'signup'
      ? 'Turn a description of a system into a diagram you can edit.'
      : mode === 'forgot'
        ? "Enter your address and we'll email you a link."
        : 'Sign in to your diagrams and the conversations behind them.'

  return (
    <div className="auth">
      <main className="auth-main">
        <a className="auth-brand" href="/" aria-label="Canvo — home">
          <span className="brand-mark" aria-hidden="true">
            <Logo size={17} />
          </span>
          <span className="brand-wordmark">Canvo</span>
        </a>

        <form className="auth-form" onSubmit={submit} noValidate>
          <h1 className="auth-title">{title}</h1>
          <p className="auth-sub">{sub}</p>

          <label className="gate-field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              autoFocus
              required
            />
          </label>

          {mode !== 'forgot' && (
            <label className="gate-field">
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                // Tells a password manager whether to offer a saved password or generate one.
                autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                minLength={mode === 'signup' ? 10 : undefined}
                aria-describedby={mode === 'signup' ? 'pw-hint' : undefined}
                required
              />
              {mode === 'signup' && (
                <small id="pw-hint">
                  At least 10 characters. A short sentence beats a clever word.
                </small>
              )}
            </label>
          )}

          {mode === 'signup' && (
            <label className="gate-field">
              <span>Confirm password</span>
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                autoComplete="new-password"
                required
              />
            </label>
          )}

          {error && (
            <p className="gate-error" role="alert">
              {error}
            </p>
          )}
          {sent && (
            <p className="gate-note" role="status">
              If that address has an account, a reset link is on its way. The link works
              once and expires in an hour.
            </p>
          )}

          <button className="gate-submit" type="submit" disabled={busy}>
            {busy && <span className="spinner" aria-hidden="true" />}
            {mode === 'signup' ? 'Create account' : mode === 'forgot' ? 'Send reset link' : 'Log in'}
          </button>

          {mode === 'login' && (
            <p className="gate-switch">
              <button type="button" onClick={() => go('forgot')}>
                Forgot your password?
              </button>
            </p>
          )}

          <p className="gate-switch">
            {mode === 'forgot' ? (
              <button type="button" onClick={() => go('login')}>
                Back to log in
              </button>
            ) : mode === 'signup' ? (
              <>
                Already have an account?{' '}
                <button type="button" onClick={() => go('login')}>
                  Log in
                </button>
              </>
            ) : (
              <>
                Don't have an account?{' '}
                <button type="button" onClick={() => go('signup')}>
                  Sign up
                </button>
              </>
            )}
          </p>
        </form>
      </main>

      {/* Product proof, not decoration — but it is a repeat of what the landing page
          already said, so it is hidden rather than stacked on a phone. */}
      <aside className="auth-aside">
        <p className="auth-aside-label">What Canvo does</p>
        <ul className="auth-proof">
          {PROOF.map(({ icon: Icon, title: t, body }) => (
            <li key={t}>
              <span className="auth-proof-icon" aria-hidden="true">
                <Icon size={16} />
              </span>
              <span>
                <strong>{t}</strong>
                <span>{body}</span>
              </span>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  )
}
