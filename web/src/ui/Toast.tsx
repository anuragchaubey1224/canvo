// Transient confirmation.
//
// Optimistic UI is a lie until something tells you it landed: the row vanishes the moment
// you confirm a delete, and without a toast there is no difference between "deleted" and
// "the request failed and we hid your diagram anyway". Every mutation on the dashboard
// reports here.
//
// Announced with aria-live="polite" so it reaches a screen reader without interrupting,
// and it is never the *only* signal — the list itself always changes too.

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Alert, Check, X } from './icons'
import { ToastContext, type Push, type Tone } from './toast-context'

interface Toast {
  id: number
  text: string
  tone: Tone
}

const LIFETIME = 4200

export function ToastHost({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)
  const timers = useRef<number[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const push = useCallback<Push>(
    (text, tone = 'info') => {
      const id = nextId.current++
      setToasts((prev) => [...prev.slice(-2), { id, text, tone }])
      timers.current.push(window.setTimeout(() => dismiss(id), LIFETIME))
    },
    [dismiss],
  )

  // A timer that fires after unmount would set state on a dead tree.
  useEffect(() => {
    const pending = timers.current
    return () => pending.forEach(clearTimeout)
  }, [])

  const value = useMemo(() => push, [push])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast--${t.tone}`}>
            {/* The glyph, not just the colour, carries the tone — colour alone fails
                both a colour-blind reader and a greyscale screenshot. */}
            <span className="toast-icon" aria-hidden="true">
              {t.tone === 'error' ? <Alert size={14} /> : <Check size={14} />}
            </span>
            <span className="toast-text">{t.text}</span>
            <button className="toast-close" onClick={() => dismiss(t.id)} aria-label="Dismiss">
              <X size={13} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
