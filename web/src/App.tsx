import { useCallback, useRef, useState } from 'react'
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

export default function App() {
  const editorRef = useRef<Editor | null>(null)
  const [input, setInput] = useState(SAMPLE_SQL)
  const [status, setStatus] = useState('Paste a SQL schema, then Generate.')
  const [busy, setBusy] = useState(false)

  const onGenerate = useCallback(async () => {
    const editor = editorRef.current
    if (!editor || busy) return

    setBusy(true)
    setStatus('Thinking…')

    // fresh canvas each run
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
        () => setStatus(`Done — ${n} shapes.`),
      )
      editor.zoomToFit()
    } catch (e) {
      setStatus(`Error: ${(e as Error).message}. Is the agent running on :8000?`)
    } finally {
      setBusy(false)
    }
  }, [input, busy])

  return (
    <div className="app">
      <aside className="panel">
        <div>
          <h1>Canvo</h1>
          <p className="tag">spec → diagram</p>
        </div>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          spellCheck={false}
          placeholder="Paste SQL DDL (CREATE TABLE …)"
        />
        <button onClick={onGenerate} disabled={busy}>
          {busy ? 'Generating…' : 'Generate'}
        </button>
        <p className="status">{status}</p>
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
