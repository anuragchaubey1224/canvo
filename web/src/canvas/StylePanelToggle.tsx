// Styles behind a button, docked to the tool strip.
//
// tldraw shows the full swatch grid whenever anything is selected. For a tool that mostly
// draws for you, that panel is a large, always-lit block of colour sitting on the canvas —
// it reads as the app's own UI competing with the diagram. It's the same panel underneath;
// it just waits to be asked for, and it lives next to the tools whose output it styles
// rather than in the opposite corner.

import { DefaultStylePanel, TldrawUiButton, useRelevantStyles } from 'tldraw'

// tldraw's own "color" icon is a filled swatch in the current style colour, which on a
// default white stroke renders as a large white disc — far heavier than every other
// glyph in the rail. A line-weight palette matches the tool icons around it.
function PaletteIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 20 20" aria-hidden="true">
      <path
        d="M10 2.75a7.25 7.25 0 0 0 0 14.5c.9 0 1.5-.62 1.5-1.4 0-.4-.17-.74-.42-1-.26-.27-.41-.6-.41-1 0-.78.63-1.4 1.41-1.4h1.42a3.75 3.75 0 0 0 3.75-3.75c0-3.34-3.25-6-7.25-6Z"
        stroke="currentColor"
        strokeWidth="1.35"
        fill="none"
      />
      <circle cx="6.6" cy="9.6" r="1" fill="currentColor" />
      <circle cx="8.9" cy="6.3" r="1" fill="currentColor" />
      <circle cx="12.7" cy="6.9" r="1" fill="currentColor" />
    </svg>
  )
}

export function StylePanelToggle({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  const styles = useRelevantStyles()

  // Nothing selected and no drawing tool active means there is nothing to style, and
  // tldraw's panel renders empty — so don't leave a dead button on the strip.
  if (!styles) return null

  return (
    <>
      <span className="tool-sep" aria-hidden="true" />
      <TldrawUiButton
        type="tool"
        isActive={open}
        title="Style"
        aria-label="Style"
        aria-expanded={open}
        onClick={onToggle}
      >
        <PaletteIcon />
      </TldrawUiButton>
      {open && (
        <div className="tool-popover">
          <DefaultStylePanel styles={styles} />
        </div>
      )}
    </>
  )
}
