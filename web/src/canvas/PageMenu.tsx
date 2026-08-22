// Pages, as a popover rather than six buttons in the header.
//
// tldraw's document model already has pages; the default menu exposes them in a panel
// that doesn't match anything else here. This is the same capability — switch, add,
// rename, duplicate, delete — in this product's own chrome.

import { useEffect, useRef, useState } from 'react'
import { useEditor, useValue } from 'tldraw'
import { Check, Copy, Pencil, Plus, Trash } from '../ui/icons'

export function PageMenu() {
  const editor = useEditor()
  const [open, setOpen] = useState(false)
  const [renaming, setRenaming] = useState<string | null>(null)
  const root = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)

  const pages = useValue('pages', () => editor.getPages(), [editor])
  const currentId = useValue('current page', () => editor.getCurrentPageId(), [editor])
  const current = pages.find((p) => p.id === currentId)

  useEffect(() => {
    if (!open) return
    const away = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false)
    }
    const escape = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      e.stopPropagation()
      if (renaming) setRenaming(null)
      else setOpen(false)
    }
    // Deferred: the pointer event that opened this is still propagating.
    const t = window.setTimeout(() => document.addEventListener('pointerdown', away))
    document.addEventListener('keydown', escape)
    return () => {
      window.clearTimeout(t)
      document.removeEventListener('pointerdown', away)
      document.removeEventListener('keydown', escape)
    }
  }, [open, renaming])

  useEffect(() => {
    if (renaming) input.current?.select()
  }, [renaming])

  const commitRename = (id: string) => {
    const next = input.current?.value.trim()
    setRenaming(null)
    if (next) editor.renamePage(id as never, next)
  }

  return (
    <div className="pages" ref={root}>
      <button
        className="chip-btn"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        title="Pages"
      >
        <span className="chip-btn-label">{current?.name ?? 'Page 1'}</span>
        <svg width="10" height="10" viewBox="0 0 16 16" aria-hidden="true">
          <path
            d="M4 6.5L8 10.5l4-4"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </svg>
      </button>

      {open && (
        <div className="pop" role="menu" aria-label="Pages">
          <p className="pop-label">Pages</p>
          {pages.map((page) => (
            <div key={page.id} className="page-row">
              {renaming === page.id ? (
                <input
                  ref={input}
                  className="page-rename"
                  defaultValue={page.name}
                  aria-label="Page name"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') commitRename(page.id)
                    if (e.key === 'Escape') setRenaming(null)
                  }}
                  onBlur={() => commitRename(page.id)}
                />
              ) : (
                <>
                  <button
                    className={`page-pick${page.id === currentId ? ' is-current' : ''}`}
                    role="menuitemradio"
                    aria-checked={page.id === currentId}
                    onClick={() => {
                      editor.setCurrentPage(page.id)
                      setOpen(false)
                    }}
                  >
                    <span className="page-tick" aria-hidden="true">
                      {page.id === currentId && <Check size={13} />}
                    </span>
                    <span className="page-name">{page.name}</span>
                  </button>
                  <span className="page-tools">
                    <button
                      onClick={() => setRenaming(page.id)}
                      aria-label={`Rename ${page.name}`}
                      title="Rename"
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      onClick={() => editor.duplicatePage(page.id)}
                      aria-label={`Duplicate ${page.name}`}
                      title="Duplicate"
                    >
                      <Copy size={13} />
                    </button>
                    <button
                      // The last page can't go: tldraw needs one, and a document with no
                      // page is not a state the rest of the app knows how to render.
                      disabled={pages.length === 1}
                      onClick={() => editor.deletePage(page.id)}
                      aria-label={`Delete ${page.name}`}
                      title={pages.length === 1 ? 'A document needs one page' : 'Delete'}
                    >
                      <Trash size={13} />
                    </button>
                  </span>
                </>
              )}
            </div>
          ))}

          <span className="pop-sep" aria-hidden="true" />
          <button
            className="pop-row"
            role="menuitem"
            onClick={() => {
              editor.createPage({ name: `Page ${pages.length + 1}` })
              setOpen(false)
            }}
          >
            <Plus size={14} />
            <span>New page</span>
          </button>
        </div>
      )}
    </div>
  )
}
