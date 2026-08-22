// The workspace: one canvas, one bar across the top of it, one copilot rail beside it.
//
// A session is a conversation *and* the diagram it produced — picking one from history
// restores both. Everything the agent does arrives over SSE and is applied to the canvas
// as it streams, so the diagram builds up in front of the user rather than appearing at
// the end.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Tldraw, type Editor as TldrawEditor, type TLComponents } from 'tldraw'
import 'tldraw/tldraw.css'
import { CanvasEmptyState } from './canvas/CanvasEmptyState'
import { Toolbar } from './canvas/Toolbar'
import { WorkspaceHeader } from './canvas/WorkspaceHeader'
import { WorkspaceContext, type SaveState, type Workspace } from './canvas/workspace-context'
import { CopilotPanel } from './chat/CopilotPanel'
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
import { Aborted, QuotaExceeded, streamAgent } from './lib/transport'
import { customShapeUtils } from './shapes'

// Defined once, outside the component: a new object each render would remount the editor.
//
// The default chrome is replaced rather than added to. tldraw's menu cluster, navigation
// panel and share panel each own a corner; our header is one bar that owns the whole top
// row, so those slots are emptied and `TopPanel` — the full-width centre slot — carries it.
const CANVAS_COMPONENTS: TLComponents = {
  Toolbar: Toolbar,
  TopPanel: WorkspaceHeader,
  MenuPanel: null,
  SharePanel: null, // zoom moved into the header
  StylePanel: null, // the style button lives in the tool strip, next to what it styles
  NavigationPanel: null,
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

const RAIL_KEY = 'canvo:rail-collapsed'

/** Fit the diagram to whatever room the canvas currently has.
 *
 * `zoomToFit()` alone was putting diagrams half off-screen: it measures against the
 * viewport bounds tldraw last recorded, and those are stale for a frame after the rail
 * collapses or a diagram loads, so it fits to the *old* column width. Re-measuring the
 * container first makes the result deterministic, and an explicit inset keeps the frame
 * off the chrome instead of flush against it.
 */
function fitToCanvas(editor: TldrawEditor | null, opts: { onlyIfOffscreen?: boolean } = {}) {
  if (!editor) return
  editor.updateViewportScreenBounds(editor.getContainer())
  const bounds = editor.getCurrentPageBounds()
  if (!bounds) return
  // After an edit, re-framing everything throws away the view the user chose. Only step
  // in when the change actually happened somewhere they can't see.
  if (opts.onlyIfOffscreen && editor.getViewportPageBounds().contains(bounds)) return
  editor.zoomToBounds(bounds, { inset: 56, animation: { duration: 180 } })
}

/** The label a selected shape shows on the canvas, so a suggestion can name it.
 *
 * Every shape type spells this differently — our node cards use `title`, frames use
 * `name`, tldraw's own geo uses `text` — and the union of their prop types has no common
 * index signature, hence the one widening cast. */
function labelOf(shape: { props?: unknown } | undefined): string {
  const props = (shape?.props ?? {}) as Record<string, unknown>
  for (const key of ['title', 'name', 'text', 'label']) {
    const v = props[key]
    if (typeof v === 'string' && v.trim()) return v.trim()
  }
  return ''
}

export default function Editor({
  sessionId,
  start,
  onNavigate,
  runsLeft,
  onRunStarted,
  onRunSettled,
}: {
  sessionId: string
  start: string | null
  onNavigate: (to: string) => void
  /** Generations left on this account, or null when unlimited. Owned by App, so the
   *  dashboard and this panel never disagree. The server is still the authority. */
  runsLeft: number | null
  /** A run is about to spend one — move the counter now, not when it finishes. */
  onRunStarted: () => void
  /** The run is over: re-read the real count from the server. */
  onRunSettled: () => void
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
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(RAIL_KEY) === '1')
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [hasShapes, setHasShapes] = useState(false)
  const [selection, setSelection] = useState<string[]>([])

  const abortRef = useRef<AbortController | null>(null)
  // True while a snapshot is being loaded onto the canvas. The store fires for every shape
  // that lands, and reporting "Unsaved changes" for the act of opening a diagram would be
  // both wrong and alarming.
  const loadingRef = useRef(true)

  useEffect(() => {
    localStorage.setItem(RAIL_KEY, collapsed ? '1' : '0')
  }, [collapsed])

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
    loadingRef.current = true
    setActive(id)
    setActiveId(id)
    setLive(null)
    setLiveStatus('')
    setSaveState('idle')
    setSelection([])

    const [loaded, snapshot, history] = await Promise.all([
      fetchMessages(id),
      fetchSnapshot(id),
      listConversations().catch(() => [] as Conversation[]),
    ])
    setMessages(loaded)
    if (history.length) setConversations(history)
    setTitle(history.find((c) => c.id === id)?.title ?? 'Untitled')

    if (!editor) {
      loadingRef.current = false
      return
    }
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
    setHasShapes(editor.getCurrentPageShapeIds().size > 0)
    // One frame, so the store events from loading land while the flag is still up.
    requestAnimationFrame(() => {
      loadingRef.current = false
    })
  }, [])

  const onMount = useCallback(
    (editor: TldrawEditor) => {
      editorRef.current = editor
      // Dark canvas is the product's default look; users can still flip it from the menu.
      editor.user.updateUserPreferences({ colorScheme: 'dark' })
      // A faint grid, so panning an infinite canvas has a frame of reference. tldraw draws
      // it in canvas space, so it scales with zoom the way a CSS background could not.
      editor.updateInstanceState({ isGridMode: true })

      let timer: number | undefined
      const unlistenDoc = editor.store.listen(
        () => {
          setHasShapes(editor.getCurrentPageShapeIds().size > 0)
          if (loadingRef.current) return
          setSaveState('unsaved')
          window.clearTimeout(timer)
          timer = window.setTimeout(() => {
            const id = getActiveId()
            if (!id) return
            setSaveState('saving')
            void saveSnapshot(id, JSON.stringify(editor.getSnapshot()))
              .then(() => setSaveState('saved'))
              .catch(() => setSaveState('error'))
          }, 800)
        },
        { scope: 'document' },
      )

      // Selection is session-scoped, and it drives what the copilot offers — so it is
      // read here rather than polled.
      const unlistenSel = editor.store.listen(
        () => {
          const names = editor
            .getSelectedShapeIds()
            .map((id) => labelOf(editor.getShape(id)))
            .filter(Boolean)
          setSelection((prev) =>
            prev.length === names.length && prev.every((n, i) => n === names[i]) ? prev : names,
          )
        },
        { scope: 'session' },
      )

      void openConversation(sessionId).finally(() => setReady(true))

      return () => {
        window.clearTimeout(timer)
        unlistenDoc()
        unlistenSel()
      }
    },
    [openConversation, sessionId],
  )

  // The URL is the source of truth: navigating between diagrams reloads this one in place.
  useEffect(() => {
    if (ready) void openConversation(sessionId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const run = useCallback(
    async (prompt: string) => {
      const editor = editorRef.current
      if (!editor || busy || !prompt) return

      let id = activeId
      if (!id) {
        const created = await createConversation()
        id = created.id
        setActive(id)
      }

      setBusy(true)
      // Reported up immediately so the counter moves while the run is in flight; the
      // authoritative number arrives from the server when it settles.
      onRunStarted()
      setDraft('')
      setMessages((prev) => [
        ...prev,
        { id: Date.now(), role: 'user', text: prompt, activity: null, created_at: '' },
      ])
      void appendMessage(id, 'user', prompt)
      if (title === 'Untitled') setTitle(prompt.slice(0, 60))

      const applier = makeApplier(editor)
      // Accumulated outside state so the final persisted trace can't miss a late event.
      const trace: RunActivity = { passes: [] }
      let drawn = 0
      let edited = false
      let answer = ''
      let stopped = false
      setLive({ passes: [] })
      setLiveStatus('Reading your request…')

      const controller = new AbortController()
      abortRef.current = controller

      const push = (patch: Partial<RunActivity>) => {
        Object.assign(trace, patch)
        setLive({ ...trace, passes: [...(trace.passes ?? [])] })
      }

      try {
        await streamAgent(
          { message: '', payload: prompt, session_id: id },
          {
            onAction: (action) => {
              applier.apply(action)
              drawn += 1
              push({ shapes: drawn })
              setLiveStatus(`Drawing — ${drawn} shape${drawn === 1 ? '' : 's'}`)
            },
            onSpec: (spec) => {
              push({ spec })
              setLiveStatus('Building the graph…')
              if (spec.title) {
                setTitle(spec.title)
                // Cosmetic: the title shown locally is already set. A failed write must not
                // surface as an unhandled rejection in the middle of a run.
                void renameConversation(id, spec.title).catch(() => {})
              }
            },
            onPlan: (plan) => {
              push({ plan })
              edited = plan.intent === 'edit'
              setLiveStatus(edited ? 'Applying the changes…' : 'Laying it out…')
            },
            onAnswer: (reply) => {
              answer = reply
              setLiveStatus('')
            },
            onRedraw: () => {
              // A Critic refine re-emits the whole diagram at wider spacing. Start a fresh
              // reconciliation pass rather than clearing — the shapes are about to be
              // updated in place, and clearing would flash the canvas empty.
              applier.restart()
              drawn = 0
            },
            onCritique: (pass) => {
              trace.passes = [...(trace.passes ?? []), pass]
              push({})
              setLiveStatus(pass.needs_refine ? 'Adjusting the layout…' : 'Reviewing the layout…')
            },
            onDone: (info) => {
              const done = info as { elapsed_s?: number } | null
              push({ elapsed_s: done?.elapsed_s })
            },
          },
          controller.signal,
        )
        // Only reconcile when this run actually drew. A run that drew nothing — a question,
        // or a stream that ended early — has an empty "seen" set, and sweeping against that
        // would delete the whole diagram.
        if (drawn) {
          applier.finish()
          // A new diagram gets framed; an edit keeps the view the user was working in.
          fitToCanvas(editor, { onlyIfOffscreen: edited })
        }
      } catch (e) {
        if (e instanceof Aborted) {
          stopped = true
          push({ stopped: true })
        } else if (e instanceof QuotaExceeded) {
          // Not a failure — the server declined to spend anything, and said why in words
          // meant for a person. Keep the prompt: the limit may be lifted, or this may be
          // the daily cap and tomorrow it works.
          push({ quota: e.message })
          setDraft(prompt)
        } else {
          push({ error: `${(e as Error).message}. Is the agent running on :8000?` })
          // A failed run must not eat what the user typed — it is usually the longest
          // thing they have written all session, and retyping it is the worst possible
          // response to a backend hiccup.
          setDraft(prompt)
        }
      } finally {
        abortRef.current = null
        const result = trace.quota
          ? trace.quota
          : trace.error
            ? 'Generation failed.'
            : stopped
              ? 'Stopped.'
              : answer || `${drawn} shape${drawn === 1 ? '' : 's'} drawn.`
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: 'assistant',
            text: result,
            // A question has no run to trace — the reply is the whole turn.
            activity: answer ? null : trace,
            created_at: '',
          },
        ])
        setLive(null)
        setLiveStatus('')
        setBusy(false)
        onRunSettled()
        void appendMessage(id, 'assistant', result, answer ? undefined : trace).then(refreshHistory)
      }
    },
    [activeId, busy, onRunSettled, onRunStarted, refreshHistory, title],
  )

  const onSend = useCallback(() => {
    // The same button stops a run in flight. Cancelling keeps whatever was drawn.
    if (busy) {
      abortRef.current?.abort()
      return
    }
    void run(draft.trim())
  }, [busy, draft, run])

  /** Re-send the prompt a failed run left in the composer. */
  const onRetry = useCallback(() => {
    const prompt = draft.trim()
    if (prompt) void run(prompt)
  }, [draft, run])

  const onRename = useCallback(
    (next: string) => {
      const id = activeId
      if (!id) return
      const previous = title
      setTitle(next)
      void renameConversation(id, next)
        .then(refreshHistory)
        .catch(() => setTitle(previous))
    },
    [activeId, refreshHistory, title],
  )

  const onDelete = useCallback(
    async (id: string) => {
      // If the delete didn't land, leave the user where they are: navigating home after a
      // failure would look exactly like success.
      try {
        await deleteConversation(id)
      } catch {
        return
      }
      const rest = await listConversations().catch(() => [])
      setConversations(rest)
      // Deleting the diagram you're looking at leaves nothing to look at — go home rather
      // than silently swapping in whichever one happened to be next.
      if (id === activeId) onNavigate('/dashboard')
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

  const workspace: Workspace = useMemo(
    () => ({
      title,
      onRename,
      saveState,
      onHome: () => onNavigate('/dashboard'),
      railOpen: !collapsed,
      onToggleRail: () => setCollapsed((c) => !c),
      busy,
    }),
    [busy, collapsed, onNavigate, onRename, saveState, title],
  )

  return (
    <div className="app" data-collapsed={collapsed}>
      <main className="stage">
        <WorkspaceContext.Provider value={workspace}>
          <Tldraw onMount={onMount} shapeUtils={customShapeUtils} components={CANVAS_COMPONENTS} />
        </WorkspaceContext.Provider>
        {ready && !hasShapes && !busy && <CanvasEmptyState railOpen={!collapsed} />}
        {!ready && <div className="boot" aria-hidden="true" />}
      </main>

      {!collapsed && (
        <CopilotPanel
          title={title}
          messages={messages}
          live={live}
          liveStatus={liveStatus}
          busy={busy}
          draft={draft}
          onDraft={setDraft}
          onSend={onSend}
          onRetry={onRetry}
          conversations={conversations}
          activeId={activeId}
          onSelect={(id) => onNavigate(`/d/${id}`)}
          onDelete={onDelete}
          onCollapse={() => setCollapsed(true)}
          onFocusDiagram={() => fitToCanvas(editorRef.current)}
          hasDiagram={hasShapes}
          selection={selection}
          runsLeft={runsLeft}
        />
      )}
    </div>
  )
}
