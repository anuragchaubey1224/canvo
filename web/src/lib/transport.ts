// Streams AgentActions from the Python agent-service over SSE.

import { apiJson } from './api'
import type { AgentAction, AgentInput, CritiqueEvent, PlanEvent, SpecEvent } from './types'

export interface StreamHandlers {
  onAction: (action: AgentAction) => void
  onSpec?: (spec: SpecEvent) => void
  onPlan?: (plan: PlanEvent) => void
  onCritique?: (critique: CritiqueEvent) => void
  /** The prompt was a question: the service answers and draws nothing. */
  onAnswer?: (reply: string) => void
  // The service draws as soon as the Drawer has a diagram, so a Critic refine arrives as
  // a replacement: clear the canvas, the actions that follow are the corrected version.
  onRedraw?: () => void
  onDone?: (info: unknown) => void
}

/** Thrown when the caller aborts, so the UI can tell "you stopped it" from "it broke". */
export class Aborted extends Error {}

/** The server declined to spend anything: this account, or the whole deployment, is out
 *  of generations. The message is written for a person and is shown as-is. */
export class QuotaExceeded extends Error {}

export async function streamAgent(
  input: AgentInput,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const { onAction, onSpec, onPlan, onCritique, onRedraw, onAnswer, onDone } = handlers
  let res: Response
  try {
    res = await apiJson('/agent/stream', 'POST', input, { signal })
  } catch (e) {
    if (signal?.aborted) throw new Aborted('stopped')
    throw e
  }
  if (res.status === 429) {
    const detail = await res
      .json()
      .then((body: { detail?: unknown }) =>
        typeof body.detail === 'string' ? body.detail : '',
      )
      .catch(() => '')
    throw new QuotaExceeded(detail || "You're out of diagram generations.")
  }
  if (!res.ok || !res.body) throw new Error(`agent responded ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    let value: Uint8Array | undefined
    let done: boolean
    try {
      ;({ value, done } = await reader.read())
    } catch (e) {
      // An abort surfaces here once the body is already streaming. Whatever was drawn
      // before it stays on the canvas — cancelling is not undoing.
      if (signal?.aborted) throw new Aborted('stopped')
      throw e
    }
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
      else if (eventType === 'redraw') onRedraw?.()
      else if (eventType === 'answer') onAnswer?.((parsed as { reply: string }).reply)
      else if (eventType === 'spec') onSpec?.(parsed as SpecEvent)
      else if (eventType === 'plan') onPlan?.(parsed as PlanEvent)
      else if (eventType === 'critique') onCritique?.(parsed as CritiqueEvent)
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
