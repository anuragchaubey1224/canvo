// One form for both sign in and sign up.
//
// Two forms would mean two places to get the error handling right, and a user who picked
// the wrong one has to retype everything. Toggling the mode keeps what they typed.
//
// Errors come straight from the server: it is written never to reveal whether an address
// has an account, so there is nothing to soften or reinterpret here.

import { useCallback, useState } from 'react'
import { AuthError, login, requestReset, signup, type Account } from '../lib/auth'

type Mode = 'signin' | 'signup' | 'forgot'

export default function AuthPage({ onSignedIn }: { onSignedIn: (account: Account) => void }) {
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)

  const submit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      if (busy) return
      setBusy(true)
      setError('')
      try {
        if (mode === 'forgot') {
          await requestReset(email)
          // Shown whether or not that address has an account — the server deliberately
          // doesn't say, and echoing a difference here would give it away.
          setSent(true)
          setBusy(false)
          return
        }
        const account = mode === 'signup' ? await signup(email, password) : await login(email, password)
        onSignedIn(account)
      } catch (err) {
        setError(
          err instanceof AuthError
            ? err.message
            : "Can't reach the agent on :8000. Start it and try again.",
        )
        setBusy(false)
      }
    },
    [busy, email, mode, onSignedIn, password],
  )

  const switchTo = (next: Mode) => {
    setMode(next)
    setError('')
    setSent(false)
  }

  return (
    <div className="gate">
      <form className="gate-card" onSubmit={submit}>
        <div className="gate-brand">
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

        <h1 className="gate-title">
          {mode === 'signup'
            ? 'Create your account'
            : mode === 'forgot'
              ? 'Reset your password'
              : 'Sign in'}
        </h1>
        <p className="gate-sub">
          {mode === 'signup'
            ? 'Your diagrams and their chats are saved to this account.'
            : mode === 'forgot'
              ? "Enter your address and we'll email you a link."
              : 'Welcome back.'}
        </p>

        <label className="field">
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
        <label className="field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            // Tells a password manager whether to offer a saved password or generate one.
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
            minLength={mode === 'signup' ? 10 : undefined}
            required
          />
          {mode === 'signup' && (
            <small>At least 10 characters. A short sentence beats a clever word.</small>
          )}
        </label>
        )}

        {error && (
          <p className="gate-error" role="alert">
            {error}
          </p>
        )}
        {sent && (
          <p className="gate-note" role="status">
            If that address has an account, a reset link is on its way. The link works once
            and expires in an hour.
          </p>
        )}

        <button className="gate-submit" type="submit" disabled={busy}>
          {busy && <span className="spinner" aria-hidden="true" />}
          {mode === 'signup' ? 'Create account' : mode === 'forgot' ? 'Send reset link' : 'Sign in'}
        </button>

        {mode === 'signin' && (
          <p className="gate-switch">
            <button type="button" onClick={() => switchTo('forgot')}>
              Forgot your password?
            </button>
          </p>
        )}

        <p className="gate-switch">
          {mode === 'forgot' ? (
            <button type="button" onClick={() => switchTo('signin')}>
              Back to sign in
            </button>
          ) : mode === 'signup' ? (
            <>
              Already have an account?{' '}
              <button type="button" onClick={() => switchTo('signin')}>
                Sign in
              </button>
            </>
          ) : (
            <>
              New here?{' '}
              <button type="button" onClick={() => switchTo('signup')}>
                Create an account
              </button>
            </>
          )}
        </p>
      </form>
    </div>
  )
}
