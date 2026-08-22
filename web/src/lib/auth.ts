// Auth client.
//
// The session lives in an httpOnly cookie, which means this file never sees or stores a
// token — there is nothing in localStorage for an XSS to steal. The only thing it has to
// get right is sending credentials on every request, which `api()` in ./api centralises.

import { api, apiJson } from './api'

export interface Account {
  id: string
  email: string
  /** Whether the address has been confirmed. Nothing is gated on it yet; it's what makes
   *  the inbox trustworthy for recovery. */
  email_verified: boolean
  created_at: string
  /** Generations spent on this account, and the allowance. `runs_limit: 0` means this
   *  deployment has no per-account limit. Both come from the server — the client shows
   *  the number, it does not decide it. */
  runs_used: number
  runs_limit: number
}

/** How many generations are left, or `null` when this deployment is unlimited. */
export function runsLeft(account: Account): number | null {
  if (!account.runs_limit) return null
  return Math.max(0, account.runs_limit - account.runs_used)
}

export class AuthError extends Error {}

/** What to show when the request never reached the server. The server's own messages are
 *  already written for people — and deliberately worded not to reveal whether an address
 *  has an account — so they are passed through untouched. This covers everything else. */
export const OFFLINE_MESSAGE = "We couldn't reach Canvo. Check your connection and try again."


async function post(path: string, body?: unknown): Promise<Response> {
  return body ? apiJson(path, 'POST', body) : api(path, { method: 'POST' })
}

/** The server's message is written to be shown as-is; it never reveals whether an
 *  account exists, so passing it straight through is safe. */
async function detail(res: Response, fallback: string): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    return typeof body.detail === 'string' ? body.detail : fallback
  } catch {
    return fallback
  }
}

export async function signup(email: string, password: string): Promise<Account> {
  const res = await post('/auth/signup', { email, password })
  if (!res.ok) throw new AuthError(await detail(res, "That didn't work. Try again."))
  return (await res.json()) as Account
}

export async function login(email: string, password: string): Promise<Account> {
  const res = await post('/auth/login', { email, password })
  if (!res.ok) throw new AuthError(await detail(res, 'Email or password is incorrect.'))
  return (await res.json()) as Account
}

export async function logout(): Promise<void> {
  await post('/auth/logout')
}

/** The current account, or null when signed out. Throws only if the agent is unreachable,
 *  so the UI can tell "signed out" apart from "backend is down". */
export async function me(): Promise<Account | null> {
  const res = await api('/auth/me')
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`auth check failed (${res.status})`)
  return (await res.json()) as Account
}


/** Ask for a reset link. Always resolves — the server answers the same way whether or not
 *  the address has an account, and the UI must not undo that by behaving differently. */
export async function requestReset(email: string): Promise<void> {
  const res = await post('/auth/forgot', { email })
  if (res.status === 429) throw new AuthError(await detail(res, 'Too many attempts.'))
}

export async function resetPassword(token: string, password: string): Promise<Account> {
  const res = await post('/auth/reset', { token, password })
  if (!res.ok) throw new AuthError(await detail(res, 'That link is no longer valid.'))
  return (await res.json()) as Account
}

export async function verifyEmail(token: string): Promise<void> {
  const res = await post('/auth/verify', { token })
  if (!res.ok) throw new AuthError(await detail(res, 'That link is no longer valid.'))
}

export async function resendVerification(): Promise<void> {
  const res = await post('/auth/verify/resend')
  if (!res.ok) throw new AuthError(await detail(res, 'Could not send it just now.'))
}
