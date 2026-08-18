// The prompt box. Grows with its content up to a ceiling, Enter sends, Shift+Enter
// breaks a line — a diagram brief is usually a paragraph, so the box has to take one
// without turning into a scrolling slit.

import { useCallback, useEffect, useRef, useState } from 'react'
import { detectKind, KIND_LABEL } from '../lib/detect'

const MIN_HEIGHT = 96
const MAX_HEIGHT = 260

export function Composer({
  value,
  onChange,
  onSend,
  busy,
  samples,
}: {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  busy: boolean
  samples: { label: string; text: string }[]
}) {
  const ref = useRef<HTMLTextAreaElement>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const kind = detectKind(value)

  // Re-measure on every change: reset to auto first, or the box can only ever grow.
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(Math.max(el.scrollHeight, MIN_HEIGHT), MAX_HEIGHT)}px`
  }, [value])

  useEffect(() => {
    if (!menuOpen) return
    const close = () => setMenuOpen(false)
    const t = window.setTimeout(() => document.addEventListener('pointerdown', close))
    return () => {
      window.clearTimeout(t)
      document.removeEventListener('pointerdown', close)
    }
  }, [menuOpen])

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
        e.preventDefault()
        onSend()
      }
    },
    [onSend],
  )

  const ready = value.trim().length > 0 && !busy

  return (
    <div className="composer">
      <textarea
        ref={ref}
        className="composer-input"
        value={value}
        rows={1}
        spellCheck={false}
        placeholder={'Describe what to create.\nEnter to send · Shift+Enter for a new line.'}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="composer-bar">
        {/* The reference puts an attachment button here. We have nothing to attach, so the
            slot carries the starters instead — they were otherwise only reachable from the
            empty state, which is exactly when you least know what to type. */}
        <div className="menu-anchor">
          <button
            className="composer-plus"
            onClick={() => setMenuOpen((v) => !v)}
            title="Starters"
            aria-label="Starters"
            aria-expanded={menuOpen}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
          {menuOpen && (
            <div className="starter-menu" role="menu">
              {samples.map((s) => (
                <button
                  key={s.label}
                  role="menuitem"
                  onClick={() => {
                    onChange(s.text)
                    setMenuOpen(false)
                    ref.current?.focus()
                  }}
                >
                  {s.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {value.trim() && <span className="kind">{KIND_LABEL[kind]}</span>}

        <button
          className="send"
          onClick={onSend}
          disabled={!ready}
          aria-label={busy ? 'Generating' : 'Send'}
        >
          {busy ? (
            <span className="spinner" aria-hidden="true" />
          ) : (
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path
                d="M8 13V3.5M8 3.5L3.5 8M8 3.5L12.5 8"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
              />
            </svg>
          )}
        </button>
      </div>
    </div>
  )
}
