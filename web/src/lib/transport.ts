// Streams AgentActions from the Python agent-service over SSE.

import type { AgentAction, AgentInput } from './types'

const API =
  (import.meta as unknown as { env?: Record<string, string | undefined> }).env
    ?.VITE_AGENT_URL ?? 'http://127.0.0.1:8000'

export async function streamAgent(
  input: AgentInput,
  onAction: (action: AgentAction) => void,
  onDone?: (info: unknown) => void,
): Promise<void> {
  const res = await fetch(`${API}/agent/stream`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(input),
  })
  if (!res.ok || !res.body) throw new Error(`agent responded ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE events are separated by a blank line.
    const events = buffer.split('\n\n')
    buffer = events.pop() ?? ''

    for (const raw of events) {
      let eventType = 'message'
      const dataLines: string[] = []
      for (const line of raw.split('\n')) {
        if (line.startsWith('event:')) eventType = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
      }
      if (!dataLines.length) continue

      const parsed = safeParse(dataLines.join('\n'))
      if (eventType === 'done') onDone?.(parsed)
      else if (parsed) onAction(parsed as AgentAction)
    }
  }
}

function safeParse(s: string): unknown {
  try {
    return JSON.parse(s)
  } catch {
    return null
  }
}
