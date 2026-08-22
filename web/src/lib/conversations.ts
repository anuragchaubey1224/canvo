// Conversation history — a session is a chat *and* the canvas it produced, so reopening
// one restores both the diagram and the trace of how it got there.

import { api, apiJson } from './api'
import type { CritiqueEvent, PlanEvent, SpecEvent } from './types'

export interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
  messages: number
  has_canvas: boolean
}

/** The trace of one run. Stored with the assistant's turn and replayed into the same
 *  blocks the user watched stream the first time — so history isn't a lossy summary. */
export interface RunActivity {
  spec?: SpecEvent | null
  plan?: PlanEvent | null
  passes?: CritiqueEvent[]
  shapes?: number
  elapsed_s?: number
  error?: string | null
  /** The user pressed stop. Whatever was drawn stays; the run just ended early. */
  stopped?: boolean
  /** The server refused to spend anything — the allowance is gone. Its own field rather
   *  than `error`, because nothing broke and there is nothing to retry. */
  quota?: string
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  text: string
  activity: RunActivity | null
  created_at: string
}

const ACTIVE_KEY = 'canvo:sid'

export function getActiveId(): string | null {
  return localStorage.getItem(ACTIVE_KEY)
}

export function setActiveId(id: string): void {
  localStorage.setItem(ACTIVE_KEY, id)
}

async function json<T>(res: Response, what: string): Promise<T> {
  if (!res.ok) throw new Error(`${what} failed (${res.status})`)
  return (await res.json()) as T
}

export async function createConversation(): Promise<Conversation> {
  const res = await api('/sessions', { method: 'POST' })
  const { id, title } = await json<{ id: string; title: string }>(res, 'new conversation')
  setActiveId(id)
  const now = new Date().toISOString()
  return { id, title, created_at: now, updated_at: now, messages: 0, has_canvas: false }
}

export async function listConversations(): Promise<Conversation[]> {
  return json<Conversation[]>(await api('/sessions'), 'history')
}

/** Both of these throw on a non-2xx, like the reads above. They used to swallow it, which
 *  meant a 404 or a dropped connection was indistinguishable from success — so a caller
 *  doing an optimistic update had no way to know it should roll back. */
export async function renameConversation(id: string, title: string): Promise<void> {
  const res = await apiJson(`/sessions/${id}`, 'PATCH', { title })
  if (!res.ok) throw new Error(`rename failed (${res.status})`)
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await api(`/sessions/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`delete failed (${res.status})`)
}

export async function fetchMessages(id: string): Promise<ChatMessage[]> {
  const res = await api(`/sessions/${id}/messages`)
  if (!res.ok) return []
  return (await res.json()) as ChatMessage[]
}

export async function appendMessage(
  id: string,
  role: 'user' | 'assistant',
  text: string,
  activity?: RunActivity,
): Promise<void> {
  await apiJson(`/sessions/${id}/messages`, 'POST', { role, text, activity: activity ?? null })
}

/** "just now" / "12m" / "3h" / "5d" — a history list needs recency, not timestamps. */
export function relativeTime(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
  return `${Math.floor(seconds / 86400)}d`
}

/** "just now" / "4m ago" / "2d ago" — `relativeTime` with the unit spelled out, for the
 *  places that show it as a sentence rather than in a column. Past a month the relative
 *  form stops being informative ("47d ago") and a date is what people actually want. */
export function agoLabel(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  const days = Math.floor(seconds / 86400)
  return days < 30 ? `${days}d ago` : new Date(iso).toLocaleDateString()
}
