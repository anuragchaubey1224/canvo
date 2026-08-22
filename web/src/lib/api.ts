// Base URL of the Python agent-service, and the one place that talks to it.
//
// `localhost`, not `127.0.0.1`, on purpose. They resolve to the same machine but browsers
// treat them as different *sites*, and the session cookie is SameSite=Lax — so a page on
// localhost:5173 calling 127.0.0.1:8000 would never send it and login would silently not
// stick. Ports don't affect site, so localhost:5173 → localhost:8000 is same-site.
// The same rule applies in production: the API has to be a subdomain of the app.
export const API =
  (import.meta as unknown as { env?: Record<string, string | undefined> }).env?.VITE_AGENT_URL ??
  'http://localhost:8000'

/** fetch with the session cookie attached.
 *
 * Every call to the service goes through here. A missed `credentials: 'include'` doesn't
 * throw — it just arrives unauthenticated and the user appears randomly signed out, which
 * is a miserable bug to find. Centralising it means it can't be forgotten. */
export async function api(path: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(`${API}${path}`, { ...init, credentials: 'include' })
  // A 401 on a request that was supposed to be authenticated means the session ended —
  // it expired, or it was signed out in another tab. The app shell listens for this and
  // drops to signed-out, rather than leaving a page whose data will never arrive.
  //
  // `/auth/*` is excluded on purpose: `/auth/me` answers 401 for "nobody is signed in",
  // which is a normal answer to a normal question, and a failed sign-in is 401 by design.
  if (res.status === 401 && !path.startsWith('/auth/')) {
    window.dispatchEvent(new Event('canvo:unauthorized'))
  }
  return res
}

/** As `api`, but for a JSON body. `init` is for the rest — chiefly an AbortSignal, so a
 *  long-running stream can be cancelled by the user. */
export function apiJson(
  path: string,
  method: string,
  body: unknown,
  init: RequestInit = {},
): Promise<Response> {
  return api(path, {
    ...init,
    method,
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
}
