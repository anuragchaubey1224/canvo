// The assistant's turn is a record of work, not prose: four named steps with a status
// and a one-line result. Detail is there but folded away — the trace matters while it
// runs and becomes noise the moment it's done, so nothing expands unless asked.

import type { RunActivity } from '../lib/conversations'

type Status = 'pending' | 'running' | 'ok' | 'warn' | 'error'

function Step({
  label,
  status,
  summary,
  children,
}: {
  label: string
  status: Status
  summary: string
  children?: React.ReactNode
}) {
  if (status === 'pending') return null
  const head = (
    <>
      <span className="step-dot" data-status={status} aria-hidden="true" />
      <span className="step-label">{label}</span>
      <span className="step-summary">{summary}</span>
    </>
  )
  // Only steps with detail become disclosures; the rest stay unclickable rows so a
  // chevron never promises something that isn't there.
  if (!children) return <div className="step">{head}</div>
  return (
    <details className="step step--open">
      <summary>{head}</summary>
      <div className="step-detail">{children}</div>
    </details>
  )
}

function issueClass(severity: string) {
  return severity === 'error' ? 'issue issue--error' : 'issue'
}

export function ActivityTrace({ activity, live }: { activity: RunActivity; live?: boolean }) {
  const { spec, plan, passes = [], shapes, error } = activity

  const specStatus: Status = spec ? 'ok' : live ? 'running' : 'pending'
  const planStatus: Status = plan ? (plan.degraded ? 'warn' : 'ok') : spec && live ? 'running' : 'pending'
  const drawStatus: Status = shapes ? 'ok' : plan && live ? 'running' : 'pending'
  const last = passes[passes.length - 1]
  const reviewStatus: Status = !passes.length
    ? shapes && live
      ? 'running'
      : 'pending'
    : last.has_issues
      ? 'warn'
      : 'ok'

  return (
    <div className="trace">
      {spec && (
        <Step
          label="Spec"
          status={specStatus}
          summary={`${spec.diagram_type ?? 'diagram'} · ${spec.components.length} components · ${spec.flow_steps} steps`}
        >
          {spec.title && <p className="detail-title">{spec.title}</p>}
          {spec.phases.length > 0 && (
            <ul className="detail-list">
              {spec.phases.map((phase) => (
                <li key={phase}>{phase}</li>
              ))}
            </ul>
          )}
          {spec.assumptions.length > 0 && (
            <>
              <p className="detail-head">
                Assumptions — filled in for you, correct anything wrong
              </p>
              <ul className="detail-list detail-list--warn">
                {spec.assumptions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </>
          )}
        </Step>
      )}

      {plan?.intent === 'edit' && (
        <Step
          label="Edit"
          status={plan.rejected.length ? 'warn' : 'ok'}
          summary={
            plan.applied.length
              ? plan.summary || `${plan.applied.length} change${plan.applied.length > 1 ? 's' : ''}`
              : 'nothing to change'
          }
        >
          {plan.applied.length > 0 && (
            <ul className="detail-list">
              {plan.applied.map((change) => (
                <li key={change}>{change}</li>
              ))}
            </ul>
          )}
          {plan.rejected.length > 0 && (
            <>
              <p className="detail-head">Not applied</p>
              <ul className="detail-list detail-list--warn">
                {plan.rejected.map((why) => (
                  <li key={why}>{why}</li>
                ))}
              </ul>
            </>
          )}
        </Step>
      )}

      {plan && (
        <Step
          label="Plan"
          status={planStatus}
          summary={`${plan.nodes} nodes · ${plan.edges} edges · ${plan.groups} groups`}
        >
          {plan.degraded && <p className="detail-error">{plan.degraded}</p>}
          {plan.fixes.length > 0 && (
            <ul className="detail-list">
              {plan.fixes.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          )}
          {plan.issues.length > 0 && (
            <ul className="detail-list">
              {plan.issues.map((i) => (
                <li key={i.kind + i.message} className={issueClass(i.severity)}>
                  {i.message}
                </li>
              ))}
            </ul>
          )}
          {!plan.degraded && !plan.fixes.length && !plan.issues.length && (
            <p className="detail-ok">Nothing to correct.</p>
          )}
        </Step>
      )}

      <Step
        label="Draw"
        status={drawStatus}
        summary={shapes ? `${shapes} shapes` : 'laying out…'}
      />

      {passes.length > 0 && (
        <Step
          label="Review"
          status={reviewStatus}
          summary={
            last.has_issues
              ? `${passes.length} pass${passes.length > 1 ? 'es' : ''} · ${last.summary}`
              : `${passes.length} pass${passes.length > 1 ? 'es' : ''} · layout clean`
          }
        >
          {passes.map((pass) => (
            <div key={pass.pass} className="pass">
              <p className="detail-head">
                Pass {pass.pass} · {pass.source === 'geometry+vision' ? 'vision + geometry' : 'geometry'}
                {pass.needs_refine && ' · widened spacing'}
              </p>
              {pass.issues.length ? (
                <ul className="detail-list">
                  {pass.issues.map((i) => (
                    <li key={i.kind + i.message} className={issueClass(i.severity)}>
                      {i.message}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="detail-ok">No issues.</p>
              )}
            </div>
          ))}
        </Step>
      )}

      {error && <p className="detail-error">{error}</p>}
    </div>
  )
}
