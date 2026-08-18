// A router for two routes.
//
// `/` is the dashboard, `/d/:id` is the editor. That is the whole surface, and pulling in
// a routing library to express it would be more configuration than code. This is the
// History API with a subscription — when there is a third or fourth route with nested
// layouts, swap it for a real router rather than growing this.

import { useCallback, useEffect, useState } from 'react'

export type Route =
  | { name: 'dashboard' }
  | { name: 'editor'; id: string; start: string | null }
  /** Reached from an emailed link, so these render whether or not anyone is signed in. */
  | { name: 'reset'; token: string }
  | { name: 'verify'; token: string }

function parse(): Route {
  const path = window.location.pathname
  const query = new URLSearchParams(window.location.search)
  if (path.startsWith('/reset')) return { name: 'reset', token: query.get('token') ?? '' }
  if (path.startsWith('/verify')) return { name: 'verify', token: query.get('token') ?? '' }

  const match = /^\/d\/([A-Za-z0-9_-]+)/.exec(path)
  if (!match) return { name: 'dashboard' }
  return {
    name: 'editor',
    id: match[1],
    // How the diagram was started, so the editor can prefill the composer.
    start: query.get('start'),
  }
}

export function useRouter() {
  const [route, setRoute] = useState<Route>(parse)

  useEffect(() => {
    const onPop = () => setRoute(parse())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const navigate = useCallback((to: string) => {
    window.history.pushState(null, '', to)
    setRoute(parse())
  }, [])

  return { route, navigate }
}
