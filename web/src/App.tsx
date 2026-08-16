import { useCallback, useMemo, useRef, useState } from 'react'
import { Tldraw, type Editor } from 'tldraw'
import 'tldraw/tldraw.css'
import { makeApplier } from './lib/applyActions'
import { customShapeUtils } from './shapes'
import { fetchSnapshot, getOrCreateSessionId, saveSnapshot } from './lib/session'
import { streamAgent } from './lib/transport'
import type { CritiqueEvent } from './lib/types'

const SAMPLE_SQL = `CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  created_at TIMESTAMP
);

CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  total NUMERIC(10,2) NOT NULL,
  status VARCHAR(32)
);`

const SAMPLE_OPENAPI = `openapi: 3.0.0
info:
  title: Shop API
paths:
  /users:
    get: { tags: [users], summary: List users }
    post: { tags: [users], summary: Create user }
  /users/{id}:
    get: { tags: [users] }
  /orders:
    get: { tags: [orders] }
    post: { tags: [orders] }
  /health:
    get: {}`

type Kind = 'sql' | 'openapi' | 'text'

function detectKind(text: string): Kind {
  if (/\bcreate\s+table\b/i.test(text)) return 'sql'
  if (/["']?(openapi|swagger)["']?\s*:/i.test(text) && text.includes('paths')) return 'openapi'
  return 'text'
}

const KIND_LABEL: Record<Kind, string> = { sql: 'SQL', openapi: 'OpenAPI', text: 'Text' }

export default function App() {
  const editorRef = useRef<Editor | null>(null)
  const sessionIdRef = useRef<string | null>(null)
  const [input, setInput] = useState(SAMPLE_SQL)
  const [status, setStatus] = useState('Paste a SQL schema or OpenAPI spec, then Generate.')
  const [isError, setIsError] = useState(false)
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState('autosave on')
  const [passes, setPasses] = useState<CritiqueEvent[]>([])

  const kind = useMemo(() => detectKind(input), [input])

  // Restore the last snapshot for this browser's session, then autosave on change.
  const onMount = useCallback((editor: Editor) => {
    editorRef.current = editor

    // Dark canvas is the product's default look (Eraser-class diagrams read dark-first);
    // users can still flip it from the canvas menu.
    editor.user.updateUserPreferences({ colorScheme: 'dark' })

    let timer: number | undefined
    const unlisten = editor.store.listen(
      () => {
        window.clearTimeout(timer)
        timer = window.setTimeout(() => {
          const id = sessionIdRef.current
          if (!id) return
          setSaved('Saving…')
          void saveSnapshot(id, JSON.stringify(editor.getSnapshot())).then(() =>
            setSaved('Saved ✓'),
          )
        }, 800)
      },
      { scope: 'document' },
    )

    void (async () => {
      try {
        const id = await getOrCreateSessionId()
        sessionIdRef.current = id
        const snap = await fetchSnapshot(id)
        if (snap) editor.loadSnapshot(JSON.parse(snap))
      } catch {
        // offline / agent down — persistence just no-ops
      }
    })()

    return () => unlisten()
  }, [])

  const onGenerate = useCallback(async () => {
    const editor = editorRef.current
    if (!editor || busy) return

    setBusy(true)
    setIsError(false)
    setPasses([])
    setStatus('Thinking…')

    const ids = Array.from(editor.getCurrentPageShapeIds())
    if (ids.length) editor.deleteShapes(ids)

    const apply = makeApplier(editor)
    let n = 0
    let refined = false
    try {
      await streamAgent(
        { message: '', payload: input, session_id: sessionIdRef.current ?? 'web' },
        (action) => {
          apply(action)
          n += 1
          setStatus(`Drawing… (${n})`)
        },
        () =>
          setStatus(
            n
              ? `Done — ${n} shapes${refined ? ' · self-corrected' : ''}.`
              : 'Nothing to draw for this input.',
          ),
        (c) => {
          setPasses((prev) => [...prev, c])
          if (c.needs_refine) refined = true
          setStatus(
            c.needs_refine
              ? `Critic: found ${c.issue_count} issue${c.issue_count !== 1 ? 's' : ''} — adjusting…`
              : 'Critic: layout clean ✓',
          )
        },
      )
      if (n) editor.zoomToFit()
    } catch (e) {
      setIsError(true)
      setStatus(`${(e as Error).message}. Is the agent running on :8000?`)
    } finally {
      setBusy(false)
    }
  }, [input, busy])

  return (
    <div className="app">
      <aside className="panel">
        <header className="brand">
          <span className="mark">Canvo</span>
          <span className="tag">spec → diagram</span>
        </header>

        <div className="field">
          <div className="field-head">
            <label htmlFor="spec">Input</label>
            <span className={`badge${kind === 'text' ? ' is-muted' : ''}`}>{KIND_LABEL[kind]}</span>
          </div>
          <textarea
            id="spec"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            spellCheck={false}
            placeholder="Paste SQL DDL (CREATE TABLE …) or an OpenAPI spec"
          />
          <div className="samples">
            <span className="samples-label">Samples</span>
            <button className="chip" onClick={() => setInput(SAMPLE_SQL)}>
              SQL
            </button>
            <button className="chip" onClick={() => setInput(SAMPLE_OPENAPI)}>
              OpenAPI
            </button>
          </div>
        </div>

        <button className="btn-primary" onClick={onGenerate} disabled={busy}>
          {busy && <span className="spinner" aria-hidden="true" />}
          {busy ? 'Generating…' : 'Generate'}
        </button>

        <p className="status" data-error={isError} aria-live="polite">
          {status}
        </p>

        {passes.length > 0 && (
          <div className="critic" aria-live="polite">
            <div className="critic-head">
              <span className="critic-title">Critic</span>
              <span className="critic-sub">self-correction</span>
            </div>
            <ol className="critic-passes">
              {passes.map((p) => (
                <li key={p.pass} className="critic-pass" data-refine={p.needs_refine}>
                  <span className="dot" aria-hidden="true" />
                  <div className="critic-body">
                    <div className="critic-line">
                      <span className="critic-pass-n">Pass {p.pass}</span>
                      <span className="critic-src">
                        {p.source === 'geometry+vision' ? 'vision + geometry' : 'geometry'}
                      </span>
                    </div>
                    {p.needs_refine ? (
                      <>
                        <p className="critic-summary">{p.summary}</p>
                        <p className="critic-note">
                          {p.issue_count} issue{p.issue_count !== 1 ? 's' : ''} → widening spacing
                        </p>
                      </>
                    ) : p.has_issues ? (
                      <p className="critic-note">
                        {p.issue_count} advisory warning{p.issue_count !== 1 ? 's' : ''} —{' '}
                        {p.summary}
                      </p>
                    ) : (
                      <p className="critic-note critic-note--ok">Layout clean ✓</p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        )}

        <footer className="foot">
          <span>SQL &amp; OpenAPI · live</span>
          <span>{saved}</span>
        </footer>
      </aside>

      <main className="canvas">
        <Tldraw onMount={onMount} shapeUtils={customShapeUtils} />
      </main>
    </div>
  )
}
