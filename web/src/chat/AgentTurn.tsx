// One generation, presented as the artefact it produced.
//
// The reference tool shows a single line per turn — icon, diagram name, "Generated" — and
// that compactness is right: a chat log of walls of text is unreadable, and what the user
// actually wants back is a thing they can click. What it doesn't tell you is what the
// model assumed or what the reviewer found, which is the part worth keeping. So: their
// headline row, our trace folded underneath it.

import type { RunActivity } from '../lib/conversations'
import { ActivityTrace } from './ActivityTrace'

function DiagramIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M2.5 2.5v11h11M5.5 11V7M8.5 11V4.5M11.5 11V8.5"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  )
}

export function AgentTurn({
  activity,
  live,
  liveStatus,
  onFocus,
}: {
  activity: RunActivity
  live?: boolean
  liveStatus?: string
  onFocus?: () => void
}) {
  const title = activity.spec?.title ?? (live ? 'Working…' : 'Diagram')
  const failed = Boolean(activity.error)

  return (
    <div className="turn turn--agent">
      <button
        className="artifact"
        onClick={onFocus}
        disabled={!onFocus || live || failed}
        title={onFocus && !live ? 'Fit this diagram on screen' : undefined}
      >
        <span className="artifact-icon" aria-hidden="true">
          <DiagramIcon />
        </span>
        <span className="artifact-title">{title}</span>
        <span className="artifact-state">
          {failed ? 'Failed' : live ? 'Generating' : 'Generated'}
        </span>
        {activity.elapsed_s != null && !live && (
          <span className="artifact-time">{activity.elapsed_s}s</span>
        )}
      </button>

      <ActivityTrace activity={activity} live={live} />

      {live && liveStatus && (
        <p className="turn-live">
          <span className="spinner spinner--sm" aria-hidden="true" />
          {liveStatus}
        </p>
      )}
    </div>
  )
}
