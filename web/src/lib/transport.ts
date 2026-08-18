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

export async function streamAgent(input: AgentInput, handlers: StreamHandlers): Promise<void> {
  const { onAction, onSpec, onPlan, onCritique, onRedraw, onAnswer, onDone } = handlers
  const res = await apiJson('/agent/stream', 'POST', input)
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
