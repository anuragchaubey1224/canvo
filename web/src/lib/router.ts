// A router for seven routes.
//
// Still the History API with a subscription rather than a routing library: there are no
// nested layouts, no loaders and no route-level code splitting beyond the one lazy import
// in App, so a library would be more configuration than code. When a route needs children
// of its own, swap this for a real router rather than growing it.

import { useCallback, useEffect, useState } from 'react'

export type Route =
  /** Public marketing page. Signed-in visitors see it too — the nav just changes. */
  | { name: 'landing' }
  | { name: 'login'; next: string | null }
  | { name: 'signup'; next: string | null }
  | { name: 'dashboard' }
  | { name: 'editor'; id: string; start: string | null }
  /** Reached from an emailed link, so these render whether or not anyone is signed in. */
  | { name: 'reset'; token: string }
  | { name: 'verify'; token: string }

/** Routes that require an account. Everything else is public. */
export function isProtected(route: Route): boolean {
  return route.name === 'dashboard' || route.name === 'editor'
}

/** Where to send someone after they sign in. Same-origin paths only: an open redirect is
 *  a phishing primitive, and `?next=https://evil.example` is exactly how it starts. */
export function safeNext(next: string | null): string {
  if (!next || !next.startsWith('/') || next.startsWith('//')) return '/dashboard'
  return next
}

/** The current path plus query, for round-tripping through a sign-in. */
export function currentPath(): string {
  return window.location.pathname + window.location.search
}

function parse(): Route {
  const path = window.location.pathname
  const query = new URLSearchParams(window.location.search)
  const next = query.get('next')

  if (path === '/' || path === '') return { name: 'landing' }
  if (path.startsWith('/login')) return { name: 'login', next }
  if (path.startsWith('/signup')) return { name: 'signup', next }
  if (path.startsWith('/dashboard')) return { name: 'dashboard' }
  if (path.startsWith('/reset')) return { name: 'reset', token: query.get('token') ?? '' }
  if (path.startsWith('/verify')) return { name: 'verify', token: query.get('token') ?? '' }

  const match = /^\/d\/([A-Za-z0-9_-]+)/.exec(path)
  if (match) {
    return {
      name: 'editor',
      id: match[1],
      // How the diagram was started, so the editor can prefill the composer.
      start: query.get('start'),
    }
  }
  // Anything else is not a route. The landing page is the honest answer for a visitor and
  // a harmless one for a signed-in user, who gets sent on to the dashboard by the nav.
  return { name: 'landing' }
}

export function useRouter() {
  const [route, setRoute] = useState<Route>(parse)

  useEffect(() => {
    const onPop = () => setRoute(parse())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const navigate = useCallback((to: string, opts: { replace?: boolean } = {}) => {
    // `replace` for redirects, so the back button doesn't bounce you off a page you were
    // never allowed to see and straight back to it.
    if (opts.replace) window.history.replaceState(null, '', to)
    else window.history.pushState(null, '', to)
    setRoute(parse())
    window.scrollTo(0, 0)
  }, [])

  return { route, navigate }
}
