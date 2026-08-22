// What a blank canvas says.
//
// Quiet on purpose: this is a workspace, not a landing page, so the guidance sits at low
// contrast in the middle of the space it is describing and gets out of the way the moment
// a shape exists. It is not interactive — the two things it names are both one click away
// in chrome that is already on screen, and a button here would just be a third copy.

export function CanvasEmptyState({ railOpen }: { railOpen: boolean }) {
  return (
    <div className="canvas-empty" aria-hidden="true">
      <p className="canvas-empty-title">Nothing on this page yet</p>
      <p className="canvas-empty-body">
        {railOpen
          ? 'Describe a system in Canvo AI on the right, or pick a tool below and draw it yourself.'
          : 'Open Canvo AI to describe a system, or pick a tool below and draw it yourself.'}
      </p>
    </div>
  )
}
