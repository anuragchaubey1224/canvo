// Canvo shell: the canvas owns the screen, and everything the product has to say lives
// in one rail on the right. A session is a conversation *and* the diagram it produced —
// picking one from history restores both.

import { useCallback, useEffect, useRef, useState } from 'react'
import { Tldraw, type Editor as TldrawEditor, type TLComponents } from 'tldraw'
import 'tldraw/tldraw.css'
import { Toolbar } from './canvas/Toolbar'
import { ZoomMenu } from './canvas/ZoomMenu'
import { ChatPanel } from './chat/ChatPanel'
import {
  appendMessage,
  createConversation,
  deleteConversation,
  fetchMessages,
  getActiveId,
  listConversations,
  renameConversation,
  setActiveId,
  type ChatMessage,
  type Conversation,
  type RunActivity,
} from './lib/conversations'
import { makeApplier } from './lib/applyActions'
import { fetchSnapshot, saveSnapshot } from './lib/session'
import { streamAgent } from './lib/transport'
import { customShapeUtils } from './shapes'

// Defined once, outside the component: a new object each render would remount the editor.
const CANVAS_COMPONENTS: TLComponents = {
  // The strip carries the style button too — styling belongs next to the tools whose
  // output it styles, which leaves the top-right corner to zoom alone.
  Toolbar: Toolbar,
  StylePanel: null,
  SharePanel: ZoomMenu, // tldraw renders this slot top-right
  NavigationPanel: null, // its zoom + minimap moved into the zoom pill
}

// Openers from the dashboard: what the user said they wanted to make, so the composer is
// already useful the moment the canvas appears.
const STARTERS: Record<string, string> = {
  sql: `CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  created_at TIMESTAMP
);

CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  total NUMERIC(10,2) NOT NULL,
  status VARCHAR(32)
);`,
  openapi: `openapi: 3.0.0
info:
  title: Shop API
paths:
  /users:
    get: { tags: [users], summary: List users }
    post: { tags: [users], summary: Create user }
  /orders:
    get: { tags: [orders] }
    post: { tags: [orders] }`,
}


/** Fit the diagram to whatever room the canvas currently has.
 *
 * `zoomToFit()` alone was putting diagrams half off-screen: it measures against the
 * viewport bounds tldraw last recorded, and those are stale for a frame after the rail
 * collapses or a diagram loads, so it fits to the *old* column width. Re-measuring the
 * container first makes the result deterministic, and an explicit inset keeps the frame
 * off the chrome instead of flush against it.
 */
function fitToCanvas(editor: TldrawEditor | null) {
  if (!editor) return
  editor.updateViewportScreenBounds(editor.getContainer())
  const bounds = editor.getCurrentPageBounds()
  if (bounds) editor.zoomToBounds(bounds, { inset: 56, animation: { duration: 180 } })
}

export default function Editor({
  sessionId,
  start,
  onNavigate,
}: {
  sessionId: string
  start: string | null
  onNavigate: (to: string) => void
}) {
  const editorRef = useRef<TldrawEditor | null>(null)
  const [ready, setReady] = useState(false)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActive] = useState<string | null>(null)
  const [title, setTitle] = useState('Untitled')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [live, setLive] = useState<RunActivity | null>(null)
  const [liveStatus, setLiveStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState(() => (start ? (STARTERS[start] ?? '') : ''))
  const [collapsed, setCollapsed] = useState(false)

  const refreshHistory = useCallback(async () => {
    try {
      setConversations(await listConversations())
    } catch {
      // agent down — history just stays as it was
    }
  }, [])

  const openConversation = useCallback(async (id: string) => {
    const editor = editorRef.current
    // Point the autosave at the new session before touching the canvas, or clearing the
    // old diagram would be written back over the one we're about to leave.
    setActive(id)
    setActiveId(id)
    setLive(null)
    setLiveStatus('')

    const [loaded, snapshot, history] = await Promise.all([
      fetchMessages(id),
      fetchSnapshot(id),
      listConversations().catch(() => [] as Conversation[]),
    ])
    setMessages(loaded)
    if (history.length) setConversations(history)
    setTitle(history.find((c) => c.id === id)?.title ?? 'Untitled')

    if (!editor) return
    const existing = Array.from(editor.getCurrentPageShapeIds())
    if (existing.length) editor.deleteShapes(existing)
    if (snapshot) {
      try {
        editor.loadSnapshot(JSON.parse(snapshot))
        fitToCanvas(editor)
      } catch {
        // a snapshot written by an older shape schema — open this one on a clean canvas
      }
    }
  }, [])

  // A new diagram is a new URL, not a swap in place — so the browser's back button and a
  // shared link both mean what they look like they mean.
  const startNew = useCallback(async () => {
    const created = await createConversation()
    onNavigate(`/d/${created.id}`)
  }, [onNavigate])

  const onMount = useCallback(
    (editor: TldrawEditor) => {
      editorRef.current = editor
      // Dark canvas is the product's default look; users can still flip it from the menu.
      editor.user.updateUserPreferences({ colorScheme: 'dark' })

      let timer: number | undefined
      const unlisten = editor.store.listen(
        () => {
          window.clearTimeout(timer)
          timer = window.setTimeout(() => {
            const id = getActiveId()
            if (id) void saveSnapshot(id, JSON.stringify(editor.getSnapshot()))
          }, 800)
        },
        { scope: 'document' },
      )

      void openConversation(sessionId).finally(() => setReady(true))

      return () => unlisten()
    },
    [openConversation, sessionId],
  )

  // The URL is the source of truth: navigating between diagrams reloads this one in place.
  useEffect(() => {
    if (ready) void openConversation(sessionId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const onSend = useCallback(async () => {
    const editor = editorRef.current
    const prompt = draft.trim()
    if (!editor || busy || !prompt) return

    let id = activeId
    if (!id) {
      const created = await createConversation()
      id = created.id
      setActive(id)
    }

    setBusy(true)
    setDraft('')
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: 'user', text: prompt, activity: null, created_at: '' },
    ])
    void appendMessage(id, 'user', prompt)
    if (title === 'Untitled') setTitle(prompt.slice(0, 60))

    const existing = Array.from(editor.getCurrentPageShapeIds())
    if (existing.length) editor.deleteShapes(existing)

    const apply = makeApplier(editor)
    // Accumulated outside state so the final persisted trace can't miss a late event.
    const trace: RunActivity = { passes: [] }
    let drawn = 0
    setLive({ passes: [] })
    setLiveStatus('Writing the spec…')

    const push = (patch: Partial<RunActivity>) => {
      Object.assign(trace, patch)
      setLive({ ...trace, passes: [...(trace.passes ?? [])] })
    }

    try {
      await streamAgent(
        { message: '', payload: prompt, session_id: id },
        {
          onAction: (action) => {
            apply(action)
            drawn += 1
            push({ shapes: drawn })
            setLiveStatus(`Drawing… ${drawn}`)
          },
          onSpec: (spec) => {
            push({ spec })
            setLiveStatus('Planning the graph…')
            if (spec.title) {
              setTitle(spec.title)
              void renameConversation(id, spec.title)
            }
          },
          onPlan: (plan) => {
            push({ plan })
            setLiveStatus('Laying it out…')
          },
          onRedraw: () => {
            const shapes = Array.from(editor.getCurrentPageShapeIds())
            if (shapes.length) editor.deleteShapes(shapes)
            drawn = 0
          },
          onCritique: (pass) => {
            trace.passes = [...(trace.passes ?? []), pass]
            push({})
            setLiveStatus(pass.needs_refine ? 'Adjusting the layout…' : 'Reviewing…')
          },
          onDone: (info) => {
            const done = info as { elapsed_s?: number } | null
            push({ elapsed_s: done?.elapsed_s })
          },
        },
      )
      if (drawn) fitToCanvas(editor)
    } catch (e) {
      push({ error: `${(e as Error).message}. Is the agent running on :8000?` })
    } finally {
      const result = trace.error
        ? 'Generation failed.'
        : `${drawn} shape${drawn === 1 ? '' : 's'} drawn.`
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, role: 'assistant', text: result, activity: trace, created_at: '' },
      ])
      setLive(null)
      setLiveStatus('')
      setBusy(false)
      void appendMessage(id, 'assistant', result, trace).then(refreshHistory)
    }
  }, [activeId, busy, draft, refreshHistory, title])

  const onDelete = useCallback(
    async (id: string) => {
      await deleteConversation(id)
      const rest = await listConversations().catch(() => [])
      setConversations(rest)
      // Deleting the diagram you're looking at leaves nothing to look at — go home rather
      // than silently swapping in whichever one happened to be next.
      if (id === activeId) onNavigate('/')
    },
    [activeId, onNavigate],
  )

  // Re-fit when the rail opens or closes, so the diagram uses whatever space it now has.
  // Two frames, not a timer: the first lets the grid column resize, the second lets
  // tldraw's own resize observer settle before we measure it.
  useEffect(() => {
    const outer = requestAnimationFrame(() =>
      requestAnimationFrame(() => fitToCanvas(editorRef.current)),
    )
    return () => cancelAnimationFrame(outer)
  }, [collapsed])

  return (
    <div className="app" data-collapsed={collapsed}>
      <main className="stage">
        <Tldraw onMount={onMount} shapeUtils={customShapeUtils} components={CANVAS_COMPONENTS} />
        {!ready && <div className="boot" aria-hidden="true" />}
        {collapsed && (
          <button className="reveal" onClick={() => setCollapsed(false)} aria-label="Show panel">
            <svg width="15" height="15" viewBox="0 0 16 16" aria-hidden="true">
              <path
                d="M10 4L6 8l4 4"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
              />
            </svg>
          </button>
        )}
      </main>

      {!collapsed && (
        <ChatPanel
          title={title}
          messages={messages}
          live={live}
          liveStatus={liveStatus}
          busy={busy}
          draft={draft}
          onDraft={setDraft}
          onSend={onSend}
          conversations={conversations}
          activeId={activeId}
          onNew={startNew}
          onSelect={(id) => onNavigate(`/d/${id}`)}
          onDelete={onDelete}
          onHome={() => onNavigate('/')}
          onCollapse={() => setCollapsed(true)}
          onFocusDiagram={() => fitToCanvas(editorRef.current)}
        />
      )}
    </div>
  )
}
