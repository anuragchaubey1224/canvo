// The command surface.
//
// This is where the product is actually used, so it gets the treatment: the box grows
// with a paragraph-length brief, the keyboard contract is stated once beneath it rather
// than hidden in a placeholder that vanishes on the first keystroke, and the placeholder
// itself changes with the state of the workspace — "describe" before anything exists,
// "change" once it does, and the selected component's name once one is picked.

import { useCallback, useEffect, useRef } from 'react'
import { detectKind, KIND_LABEL } from '../lib/detect'
import { Send, Stop } from '../ui/icons'

const MIN_HEIGHT = 76
const MAX_HEIGHT = 240

export function Composer({
  value,
  onChange,
  onSend,
  busy,
  hasDiagram,
  selection,
  runsLeft,
}: {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  busy: boolean
  /** Drives the placeholder: a follow-up edits the diagram rather than replacing it. */
  hasDiagram: boolean
  /** Names of the shapes selected on the canvas, if any. */
  selection: string[]
  /** Generations remaining, or null when this deployment has no limit. The server is
   *  still the one that decides; this only stops the user finding out by being refused. */
  runsLeft: number | null
}) {
  const ref = useRef<HTMLTextAreaElement>(null)
  const kind = detectKind(value)

  // Re-measure on every change: reset to auto first, or the box can only ever grow.
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(Math.max(el.scrollHeight, MIN_HEIGHT), MAX_HEIGHT)}px`
  }, [value])

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // tldraw binds single letters to tools on the document. Without this, typing "r" in
      // a brief switches the canvas to the rectangle tool behind you.
      e.stopPropagation()
      if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
        e.preventDefault()
        onSend()
      }
    },
    [onSend],
  )

  const spent = runsLeft === 0

  const placeholder = spent
    ? 'No generations left on this account'
    : busy
    ? 'Working…'
    : selection.length === 1
      ? `Ask Canvo to change ${selection[0]}…`
      : selection.length > 1
        ? `Ask Canvo to change ${selection.length} selected components…`
        : hasDiagram
          ? 'Describe a change — "add a Redis cache in front of the API"'
          : 'Describe a system to diagram…'

  const ready = value.trim().length > 0 && !busy && !spent

  return (
    <div className={`composer${busy ? ' is-busy' : ''}${spent ? ' is-spent' : ''}`}>
      {selection.length > 0 && !busy && (
        // Context the prompt will be read against, stated before it's typed rather than
        // discovered afterwards.
        <p className="composer-context">
          <span className="composer-context-dot" aria-hidden="true" />
          {selection.length === 1
            ? `${selection[0]} selected`
            : `${selection.length} components selected`}
        </p>
      )}

      <textarea
        ref={ref}
        className="composer-input"
        disabled={spent}
        value={value}
        rows={1}
        spellCheck={false}
        placeholder={placeholder}
        aria-label={hasDiagram ? 'Describe a change to this diagram' : 'Describe a system to diagram'}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
      />

      <div className="composer-bar">
        <span className="composer-hint">
          {runsLeft !== null && !busy && (
            // Counted down rather than announced at the end: being refused after writing
            // a paragraph is a worse way to learn there was a limit.
            <span className={`allowance${spent ? ' is-spent' : ''}`}>
              {spent ? 'No generations left' : `${runsLeft} left`}
            </span>
          )}
          {value.trim() ? (
            // The service picks its input route from the text; showing which one it landed
            // on means a pasted schema visibly *is* a schema before you send it.
            <>
              <span className="kind">{KIND_LABEL[kind]}</span>
              <span className="composer-keys">
                <kbd>↵</kbd> send <kbd>⇧↵</kbd> newline
              </span>
            </>
          ) : (
            <span className="composer-keys">
              <kbd>↵</kbd> send <kbd>⇧↵</kbd> newline
            </span>
          )}
        </span>

        <button
          className="send"
          onClick={onSend}
          disabled={!ready}
          title={busy ? 'Generating…' : 'Send'}
          aria-label={busy ? 'Generating' : 'Send'}
        >
          {busy ? <Stop size={13} /> : <Send size={15} />}
        </button>
      </div>
    </div>
  )
}
