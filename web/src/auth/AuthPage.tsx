// One form for both sign in and sign up.
//
// Two forms would mean two places to get the error handling right, and a user who picked
// the wrong one has to retype everything. Toggling the mode keeps what they typed.
//
// Errors come straight from the server: it is written never to reveal whether an address
// has an account, so there is nothing to soften or reinterpret here.

import { useCallback, useState } from 'react'
import { AuthError, login, signup, type Account } from '../lib/auth'

type Mode = 'signin' | 'signup'

export default function AuthPage({ onSignedIn }: { onSignedIn: (account: Account) => void }) {
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      if (busy) return
      setBusy(true)
      setError('')
      try {
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
          {mode === 'signup' ? 'Create your account' : 'Sign in'}
        </h1>
        <p className="gate-sub">
          {mode === 'signup'
            ? 'Your diagrams and their chats are saved to this account.'
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

        {error && (
          <p className="gate-error" role="alert">
            {error}
          </p>
        )}

        <button className="gate-submit" type="submit" disabled={busy}>
          {busy && <span className="spinner" aria-hidden="true" />}
          {mode === 'signup' ? 'Create account' : 'Sign in'}
        </button>

        <p className="gate-switch">
          {mode === 'signup' ? (
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
