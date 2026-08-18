// Canvas persistence for a session. Which session is active, and its conversation, are
// owned by conversations.ts — this file only moves the tldraw snapshot.

import { api, apiJson } from './api'

export async function fetchSnapshot(id: string): Promise<string | null> {
  const res = await api(`/sessions/${id}/snapshot`)
  if (!res.ok) return null
  const data = (await res.json()) as { snapshot: string | null }
  return data.snapshot
}

export async function saveSnapshot(id: string, snapshot: string): Promise<void> {
  await apiJson(`/sessions/${id}/snapshot`, 'PUT', { snapshot })
}
