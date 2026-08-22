// One run of the agent, presented as the artefact it produced.
//
// The diagram is the thing the user wanted, so the turn leads with it: what was made, how
// big it is, and a way to put it back on screen. The trace of *how* — spec, plan, draw,
// review — sits underneath, folded, because it matters while it runs and becomes reference
// material the moment it's done.
//
// Every number here comes from an event the service actually sent. Nothing is estimated,
// and no step is shown as complete before its event arrives.

import type { RunActivity } from '../lib/conversations'
import { Alert, Board, Refresh, Shield } from '../ui/icons'
import { ActivityTrace } from './ActivityTrace'

/** "8 nodes · 7 connections · 1 review pass" — the shape of the result, from the plan. */
function resultLine(activity: RunActivity): string | null {
  const { plan, shapes, passes = [] } = activity
  const parts: string[] = []
  if (plan?.intent === 'edit') {
    if (plan.applied.length) {
      parts.push(`${plan.applied.length} change${plan.applied.length === 1 ? '' : 's'}`)
    }
  } else if (plan) {
    parts.push(`${plan.nodes} node${plan.nodes === 1 ? '' : 's'}`)
    parts.push(`${plan.edges} connection${plan.edges === 1 ? '' : 's'}`)
  } else if (shapes) {
    parts.push(`${shapes} shape${shapes === 1 ? '' : 's'}`)
  }
  if (passes.length) {
    parts.push(`${passes.length} review pass${passes.length === 1 ? '' : 'es'}`)
  }
  return parts.length ? parts.join(' · ') : null
}

export function AgentTurn({
  activity,
  live,
  liveStatus,
  fallbackTitle,
  onFocus,
  onRetry,
}: {
  activity: RunActivity
  live?: boolean
  liveStatus?: string
  /** The conversation's name. An edit produces no spec, so without this the row would
   *  lose the diagram's title and show the edit summary in its place. */
  fallbackTitle?: string
  onFocus?: () => void
  /** Offered only on a failed turn, and only for the most recent one. */
  onRetry?: () => void
}) {
  const edited = activity.plan?.intent === 'edit'
  const title = activity.spec?.title ?? fallbackTitle ?? (live ? 'Working…' : 'Diagram')
  const failed = Boolean(activity.error)
  const stopped = activity.stopped === true
  const result = resultLine(activity)

  if (activity.quota) {
    return (
      <div className="turn turn--agent">
        <div className="result result--quota" role="status">
          <span className="result-icon" aria-hidden="true">
            <Shield size={16} />
          </span>
          <div className="result-body">
            <p className="result-title">Out of generations</p>
            <p className="result-sub">{activity.quota}</p>
          </div>
        </div>
      </div>
    )
  }

  if (failed) {
    return (
      <div className="turn turn--agent">
        <div className="result result--error" role="alert">
          <span className="result-icon" aria-hidden="true">
            <Alert size={16} />
          </span>
          <div className="result-body">
            <p className="result-title">Couldn't generate that diagram</p>
            <p className="result-sub">
              Your prompt is still in the box below, so nothing was lost.
            </p>
          </div>
          {onRetry && (
            <button className="result-action" onClick={onRetry}>
              <Refresh size={14} />
              Try again
            </button>
          )}
        </div>
        {/* The technical reason, folded away: useful when it's your own backend, noise
            when it isn't. */}
        <details className="detail-fold">
          <summary>Technical detail</summary>
          <p className="detail-error">{activity.error}</p>
        </details>
      </div>
    )
  }

  return (
    <div className="turn turn--agent">
      <div className={`result${live ? ' result--live' : ''}`}>
        <span className="result-icon" aria-hidden="true">
          <Board size={16} />
        </span>
        <p className="result-title">
          {live ? title : stopped ? 'Stopped' : edited ? 'Diagram updated' : 'Diagram generated'}
        </p>
        {activity.elapsed_s != null && !live && (
          <span className="result-time">{activity.elapsed_s}s</span>
        )}
        <p className="result-sub">
          {live
            ? liveStatus || 'Starting…'
            : stopped
              ? `Kept what was drawn before you stopped${result ? ` — ${result}` : ''}.`
              : result || title}
        </p>
        {!live && onFocus && (
          <button className="result-action" onClick={onFocus} title="Fit this diagram on screen">
            Show on canvas
          </button>
        )}
      </div>

      <ActivityTrace activity={activity} live={live} />
    </div>
  )
}
