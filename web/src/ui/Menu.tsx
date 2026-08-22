// A "…" menu that behaves the way every other one does: arrows move, Enter picks, Esc
// closes and puts focus back on the trigger, and clicking anywhere else dismisses it.
//
// Rolling this rather than adding a menu library is a deliberate trade — one dropdown on
// one screen does not justify a dependency, and the WAI-ARIA menu-button pattern is about
// sixty lines. If a second, richer menu appears, replace this rather than growing it.

import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'

export interface MenuItem {
  label: string
  icon: ReactNode
  onSelect: () => void
  destructive?: boolean
}

export default function Menu({
  items,
  label,
  trigger,
  className = '',
}: {
  items: MenuItem[]
  /** Accessible name for the trigger — "More actions for Checkout service". */
  label: string
  trigger: ReactNode
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const root = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const id = useId()

  const close = useCallback(
    (restoreFocus = true) => {
      setOpen(false)
      if (restoreFocus) triggerRef.current?.focus()
    },
    [],
  )

  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false)
    }
    // Scrolling the list out from under an open menu leaves it floating over unrelated
    // rows, so it closes with the first scroll instead of following.
    const onScroll = () => setOpen(false)
    document.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('scroll', onScroll, true)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('scroll', onScroll, true)
    }
  }, [open])

  const openAt = (index: number) => {
    setActive(index)
    setOpen(true)
  }

  const onTriggerKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      openAt(0)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      openAt(items.length - 1)
    }
  }

  const onMenuKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.stopPropagation()
      close()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => (i + 1) % items.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => (i - 1 + items.length) % items.length)
    } else if (e.key === 'Home') {
      e.preventDefault()
      setActive(0)
    } else if (e.key === 'End') {
      e.preventDefault()
      setActive(items.length - 1)
    } else if (e.key === 'Tab') {
      // Closing while focus is still on a menu item would hand the browser a tab stop
      // that is about to unmount, and focus lands on <body>. Return it to the trigger
      // and let Tab continue from a node that still exists.
      e.preventDefault()
      close()
    }
  }

  return (
    <div ref={root} className={`menu ${className}`.trim()}>
      <button
        ref={triggerRef}
        type="button"
        className="menu-trigger"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => (open ? close() : openAt(0))}
        onKeyDown={onTriggerKeyDown}
      >
        {trigger}
      </button>

      {open && (
        <div id={id} className="menu-list" role="menu" aria-label={label} onKeyDown={onMenuKeyDown}>
          {items.map((item, i) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              className={`menu-item${item.destructive ? ' menu-item--danger' : ''}`}
              // Roving tabindex: the menu is one tab stop, arrows move within it.
              tabIndex={i === active ? 0 : -1}
              ref={(el) => {
                if (i === active) el?.focus()
              }}
              onMouseEnter={() => setActive(i)}
              onClick={() => {
                close(false)
                item.onSelect()
              }}
            >
              <span className="menu-item-icon" aria-hidden="true">
                {item.icon}
              </span>
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
