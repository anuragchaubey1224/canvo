// Canvas persistence for a session. Which session is active, and its conversation, are
// owned by conversations.ts — this file only moves the tldraw snapshot.

import { API } from './api'

export async function fetchSnapshot(id: string): Promise<string | null> {
  const res = await fetch(`${API}/sessions/${id}/snapshot`)
  if (!res.ok) return null
  const data = (await res.json()) as { snapshot: string | null }
  return data.snapshot
}

export async function saveSnapshot(id: string, snapshot: string): Promise<void> {
  await fetch(`${API}/sessions/${id}/snapshot`, {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ snapshot }),
  })
}
