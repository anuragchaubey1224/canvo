// Session persistence: create/lookup a session and save/restore the canvas snapshot.

import { API } from './api'

const SID_KEY = 'canvo:sid'

export async function getOrCreateSessionId(): Promise<string> {
  const existing = localStorage.getItem(SID_KEY)
  if (existing) return existing

  const res = await fetch(`${API}/sessions`, { method: 'POST' })
  if (!res.ok) throw new Error(`session create failed (${res.status})`)
  const { id } = (await res.json()) as { id: string }
  localStorage.setItem(SID_KEY, id)
  return id
}

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
