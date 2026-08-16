import { useCallback, useMemo, useRef, useState } from 'react'
import { Tldraw, type Editor } from 'tldraw'
import 'tldraw/tldraw.css'
import { makeApplier } from './lib/applyActions'
import { streamAgent } from './lib/transport'

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
  const [input, setInput] = useState(SAMPLE_SQL)
  const [status, setStatus] = useState('Paste a SQL schema or OpenAPI spec, then Generate.')
  const [isError, setIsError] = useState(false)
  const [busy, setBusy] = useState(false)

  const kind = useMemo(() => detectKind(input), [input])

  const onGenerate = useCallback(async () => {
    const editor = editorRef.current
    if (!editor || busy) return

    setBusy(true)
    setIsError(false)
    setStatus('Thinking…')

    const ids = Array.from(editor.getCurrentPageShapeIds())
    if (ids.length) editor.deleteShapes(ids)

    const apply = makeApplier(editor)
    let n = 0
    try {
      await streamAgent(
        { message: '', payload: input, session_id: 'web' },
        (action) => {
          apply(action)
          n += 1
          setStatus(`Drawing… (${n})`)
        },
        () => setStatus(n ? `Done — ${n} shapes.` : 'Nothing to draw for this input.'),
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

        <footer className="foot">
          <span>SQL & OpenAPI · live</span>
          <span>Text → LLM soon</span>
        </footer>
      </aside>

      <main className="canvas">
        <Tldraw
          onMount={(editor) => {
            editorRef.current = editor
          }}
        />
      </main>
    </div>
  )
}
