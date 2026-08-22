// Route shell + auth gate.
//
// Nothing behind the gate renders until we know who is asking. The alternative — showing
// the dashboard and letting its requests 401 — flashes an empty app at a signed-in user on
// every reload, and leaves a signed-out one staring at errors instead of a sign-in form.
//
// Protection is decided here, in one place, rather than in each page: a route that forgets
// to check is a route that leaks, and there is no way to forget if the check is the shell.

import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import AuthPage from './auth/AuthPage'
import { ResetPage, VerifyPage } from './auth/LinkPage'
import Dashboard from './dashboard/Dashboard'
import Landing from './landing/Landing'
import { me, runsLeft, type Account } from './lib/auth'
import { currentPath, isProtected, safeNext, useRouter } from './lib/router'

// Split, not eagerly imported: the editor pulls in tldraw, which is the overwhelming
// majority of the bundle. A visitor reading the landing page has no canvas on screen, and
// making them download the whole editor first is a second of nothing.
const Editor = lazy(() => import('./Editor'))

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

  // The generation allowance is owned here, so the dashboard and the workspace always
  // show the same number. A run bumps it optimistically the moment it starts — waiting
  // for the round trip would leave the counter stale for the length of a generation —
  // and re-reads the truth when it settles.
  const bumpRuns = useCallback(() => {
    setSession((s) =>
      s.state === 'in'
        ? { ...s, account: { ...s.account, runs_used: s.account.runs_used + 1 } }
        : s,
    )
  }, [])

  // A session can end while the tab is open — it expires, or it is signed out elsewhere.
  // `api()` raises this when a request that should have been authenticated comes back 401,
  // so the app drops to signed-out instead of showing a page whose data will never load.
  useEffect(() => {
    const onExpired = () => setSession({ state: 'out' })
    window.addEventListener('canvo:unauthorized', onExpired)
    return () => window.removeEventListener('canvo:unauthorized', onExpired)
  }, [])

  // Redirects live in an effect, not in render: navigating during render is a state update
  // inside another component's render pass, and React is right to complain about it.
  const signedIn = session.state === 'in'
  useEffect(() => {
    if (session.state === 'checking' || session.state === 'unreachable') return
    if (!signedIn && isProtected(route)) {
      // Remember where they were headed so signing in finishes the journey.
      navigate(`/login?next=${encodeURIComponent(currentPath())}`, { replace: true })
      return
    }
    if (signedIn && (route.name === 'login' || route.name === 'signup')) {
      navigate(safeNext(route.next), { replace: true })
    }
  }, [navigate, route, session.state, signedIn])

  if (session.state === 'checking') return <div className="gate" aria-busy="true" />

  // Emailed links resolve before everything else: a reset link is for someone who cannot
  // sign in, and a verification link is usually opened in a different browser.
  if (route.name === 'reset') {
    return (
      <ResetPage
        token={route.token}
        onSignedIn={(account) => {
          setSession({ state: 'in', account })
          navigate('/dashboard', { replace: true })
        }}
        onGiveUp={() => navigate('/login', { replace: true })}
      />
    )
  }
  if (route.name === 'verify') {
    return (
      <VerifyPage
        token={route.token}
        onDone={() => {
          void check() // pick up email_verified without a reload
          navigate(signedIn ? '/dashboard' : '/login', { replace: true })
        }}
      />
    )
  }

  if (session.state === 'unreachable') {
    return (
      <div className="gate">
        <div className="gate-card">
          <h1 className="gate-title">Canvo is unreachable</h1>
          <p className="gate-sub">
            We can't reach the service right now. Check your connection, then try again.
          </p>
          <button className="gate-submit" onClick={() => void check()}>
            Try again
          </button>
        </div>
      </div>
    )
  }

  // Public. The nav reflects whether anyone is signed in, so one page serves both.
  if (route.name === 'landing') {
    return (
      <Landing
        account={signedIn ? session.account : null}
        onNavigate={navigate}
      />
    )
  }

  if (route.name === 'login' || route.name === 'signup') {
    // Signed-in visitors are on their way to the dashboard; the effect above has already
    // fired, and rendering the form for one frame would flash a sign-in box at them.
    if (signedIn) return <div className="gate" aria-busy="true" />
    return (
      <AuthPage
        mode={route.name}
        onSignedIn={(account) => {
          setSession({ state: 'in', account })
          navigate(safeNext(route.next), { replace: true })
        }}
        onNavigate={navigate}
        next={route.next}
      />
    )
  }

  // Everything below is protected; the effect above redirects, and this renders the gate
  // for the frame in between rather than a page with no data.
  if (!signedIn) return <div className="gate" aria-busy="true" />

  const signedOut = () => {
    setSession({ state: 'out' })
    navigate('/')
  }

  if (route.name === 'editor') {
    // Keyed on the id so switching diagrams remounts the editor with a clean canvas
    // rather than leaving the previous one's shapes to be cleared mid-flight.
    return (
      <Suspense fallback={<div className="gate" aria-busy="true" />}>
        <Editor
          key={route.id}
          sessionId={route.id}
          start={route.start}
          onNavigate={navigate}
          runsLeft={runsLeft(session.account)}
          onRunStarted={bumpRuns}
          onRunSettled={() => void check()}
        />
      </Suspense>
    )
  }
  return <Dashboard onNavigate={navigate} account={session.account} onSignedOut={signedOut} />
}
