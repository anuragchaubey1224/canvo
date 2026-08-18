// The two pages you land on from an email: set a new password, or confirm an address.
//
// Both render signed out. A reset link is often opened on a different device from the one
// that asked for it, and a verification link is regularly clicked from a mail app's own
// browser — gating either behind a session would strand exactly the people they're for.

import { useCallback, useEffect, useState } from 'react'
import { resetPassword, verifyEmail, AuthError, type Account } from '../lib/auth'

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="gate">
      <div className="gate-card">
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
        {children}
      </div>
    </div>
  )
}

export function ResetPage({
  token,
  onSignedIn,
  onGiveUp,
}: {
  token: string
  onSignedIn: (account: Account) => void
  onGiveUp: () => void
}) {
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
        onSignedIn(await resetPassword(token, password))
      } catch (err) {
        setError(
          err instanceof AuthError ? err.message : "Can't reach the agent on :8000.",
        )
        setBusy(false)
      }
    },
    [busy, onSignedIn, password, token],
  )

  if (!token) {
    return (
      <Shell>
        <h1 className="gate-title">That link is incomplete</h1>
        <p className="gate-sub">Ask for a new one from the sign-in page.</p>
        <button className="gate-submit" onClick={onGiveUp}>
          Back to sign in
        </button>
      </Shell>
    )
  }

  return (
    <Shell>
      <form onSubmit={submit} style={{ display: 'contents' }}>
        <h1 className="gate-title">Choose a new password</h1>
        <p className="gate-sub">
          This signs you in here and signs you out everywhere else.
        </p>

        <label className="field">
          <span>New password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={10}
            autoFocus
            required
          />
          <small>At least 10 characters. A short sentence beats a clever word.</small>
        </label>

        {error && (
          <p className="gate-error" role="alert">
            {error}
          </p>
        )}

        <button className="gate-submit" type="submit" disabled={busy}>
          {busy && <span className="spinner" aria-hidden="true" />}
          Set password
        </button>
        <p className="gate-switch">
          <button type="button" onClick={onGiveUp}>
            Back to sign in
          </button>
        </p>
      </form>
    </Shell>
  )
}

export function VerifyPage({ token, onDone }: { token: string; onDone: () => void }) {
  const [state, setState] = useState<'working' | 'ok' | 'failed'>('working')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) {
      setState('failed')
      setError('That link is incomplete.')
      return
    }
    void verifyEmail(token)
      .then(() => setState('ok'))
      .catch((err) => {
        setState('failed')
        setError(err instanceof AuthError ? err.message : "Can't reach the agent on :8000.")
      })
  }, [token])

  return (
    <Shell>
      <h1 className="gate-title">
        {state === 'working' ? 'Confirming…' : state === 'ok' ? 'Email confirmed' : "That didn't work"}
      </h1>
      <p className="gate-sub">
        {state === 'ok'
          ? 'You can recover this account by email if you ever lose your password.'
          : state === 'failed'
            ? error
            : 'One moment.'}
      </p>
      {state !== 'working' && (
        <button className="gate-submit" onClick={onDone}>
          Continue
        </button>
      )}
    </Shell>
  )
}
