// A modal for the one thing on the dashboard that cannot be undone.
//
// Deleting a diagram takes the canvas *and* the conversation that produced it, and there
// is no soft-delete behind it — so the dialog is the recovery mechanism, which is why the
// safe choice is what's focused when it opens and Esc is wired to it.

import { useCallback, useEffect, useRef } from 'react'

export interface ConfirmProps {
  title: string
  body: string
  confirmLabel: string
  /** Styles the confirm button as destructive and announces it as such. */
  destructive?: boolean
  onConfirm: () => void
  onCancel: () => void
}

const FOCUSABLE = 'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

export default function ConfirmDialog({
  title,
  body,
  confirmLabel,
  destructive = false,
  onConfirm,
  onCancel,
}: ConfirmProps) {
  const card = useRef<HTMLDivElement>(null)
  const cancel = useRef<HTMLButtonElement>(null)
  // Whatever the user was on when this opened — focus goes back there on close, so a
  // keyboard user is not dumped at the top of the document.
  const restoreTo = useRef<HTMLElement | null>(null)

  useEffect(() => {
    restoreTo.current = document.activeElement as HTMLElement | null
    cancel.current?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previousOverflow
      restoreTo.current?.focus?.()
    }
  }, [])

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onCancel()
        return
      }
      if (e.key !== 'Tab') return
      // Trap: a modal you can Tab out of leaves the page behind it operable while it
      // looks disabled.
      const nodes = Array.from(card.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])
      if (nodes.length === 0) return
      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    },
    [onCancel],
  )

  return (
    <div className="scrim" onMouseDown={onCancel} onKeyDown={onKeyDown}>
      <div
        ref={card}
        className="dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        aria-describedby="dialog-body"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <h2 id="dialog-title" className="dialog-title">
          {title}
        </h2>
        <p id="dialog-body" className="dialog-body">
          {body}
        </p>
        <div className="dialog-actions">
          <button ref={cancel} className="btn btn--ghost" onClick={onCancel}>
            Cancel
          </button>
          <button
            className={destructive ? 'btn btn--danger' : 'btn btn--primary'}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
