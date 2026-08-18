// Route shell + auth gate.
//
// Nothing renders until we know who is asking. The alternative — showing the dashboard and
// letting its requests 401 — flashes an empty app at a signed-in user on every reload, and
// leaves a signed-out one staring at errors instead of a sign-in form.

import { useCallback, useEffect, useState } from 'react'
import AuthPage from './auth/AuthPage'
import Dashboard from './dashboard/Dashboard'
import Editor from './Editor'
import { me, type Account } from './lib/auth'
import { useRouter } from './lib/router'

type Session =
  | { state: 'checking' }
  | { state: 'out' }
  | { state: 'in'; account: Account }
  | { state: 'unreachable' }

export default function App() {
  const { route, navigate } = useRouter()
  const [session, setSession] = useState<Session>({ state: 'checking' })

  const check = useCallback(async () => {
    try {
      const account = await me()
      setSession(account ? { state: 'in', account } : { state: 'out' })
    } catch {
      setSession({ state: 'unreachable' })
    }
  }, [])

  useEffect(() => {
    void check()
  }, [check])

  if (session.state === 'checking') return <div className="gate" aria-busy="true" />

  if (session.state === 'unreachable') {
    return (
      <div className="gate">
        <div className="gate-card">
          <h1 className="gate-title">Agent unreachable</h1>
          <p className="gate-sub">
            Canvo can't reach the service on :8000. Start it, then reload.
          </p>
          <button className="gate-submit" onClick={() => void check()}>
            Try again
          </button>
        </div>
      </div>
    )
  }

  if (session.state === 'out') {
    return (
      <AuthPage
        onSignedIn={(account) => {
          setSession({ state: 'in', account })
          // Land on the dashboard rather than whatever URL sent them here — that diagram
          // may well belong to a different account.
          navigate('/')
        }}
      />
    )
  }

  const signedOut = () => {
    setSession({ state: 'out' })
    navigate('/')
  }

  if (route.name === 'editor') {
    // Keyed on the id so switching diagrams remounts the editor with a clean canvas
    // rather than leaving the previous one's shapes to be cleared mid-flight.
    return (
      <Editor key={route.id} sessionId={route.id} start={route.start} onNavigate={navigate} />
    )
  }
  return <Dashboard onNavigate={navigate} account={session.account} onSignedOut={signedOut} />
}
