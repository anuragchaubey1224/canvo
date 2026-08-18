// Styles behind a button, docked to the tool rail.
//
// tldraw shows the full swatch grid whenever anything is selected. For a tool that mostly
// draws for you, that panel is a large, always-lit block of colour sitting on the canvas —
// it reads as the app's own UI competing with the diagram. It's the same panel underneath;
// it just waits to be asked for, and it lives next to the tools whose output it styles
// rather than in the opposite corner.

import { DefaultStylePanel, TldrawUiButton, TldrawUiButtonIcon, useRelevantStyles } from 'tldraw'

export function StylePanelToggle({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  const styles = useRelevantStyles()

  // Nothing selected and no drawing tool active means there is nothing to style, and
  // tldraw's panel renders empty — so don't leave a dead button on the rail.
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
        <TldrawUiButtonIcon icon="color" />
      </TldrawUiButton>
      {open && (
        <div className="tool-popover">
          <DefaultStylePanel styles={styles} />
        </div>
      )}
    </>
  )
}
