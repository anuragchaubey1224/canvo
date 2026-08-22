// The product, shown rather than described.
//
// This is a recreation of the workspace, not a screenshot and not a marketing
// illustration: the same chrome, the same node cards, the same four-stage trace, drawn
// with the same design tokens. Recreating it costs a few hundred bytes; mounting the real
// editor would cost 1.7 MB of tldraw on a page where nobody has asked for a canvas yet.
//
// Everything it depicts is what a real run produces. The stages are the ones the agent
// actually emits, in the order it emits them.

import { useEffect, useRef, useState } from 'react'
import { Board, Home, Sparkle } from '../ui/icons'

export interface DemoNode {
  id: string
  label: string
  sub: string
  accent: string
  /** Grid placement, in the demo's own 12 × 8 cell space. */
  col: number
  row: number
  span?: number
  /** Which beat of the animation this node arrives on. */
  beat: number
  /** Arrived as part of a refinement rather than the first draw. */
  added?: boolean
}

export interface DemoEdge {
  from: string
  to: string
  label?: string
  beat: number
  added?: boolean
}

export interface DemoScript {
  prompt: string
  title: string
  /** The four stages, in the order the service emits them. */
  stages: string[]
  result: string
  nodes: DemoNode[]
  edges: DemoEdge[]
}

const BEAT = 620

/** Plays once when it scrolls into view; jumps to the end for anyone who has asked for
 *  less motion, so the finished diagram is always what they get. */
function usePlayback(steps: number, host: React.RefObject<HTMLDivElement | null>) {
  const [beat, setBeat] = useState(0)

  useEffect(() => {
    const el = host.current
    if (!el) return
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduced) {
      setBeat(steps)
      return
    }
    let timers: number[] = []
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return
        observer.disconnect()
        timers = Array.from({ length: steps }, (_, i) =>
          window.setTimeout(() => setBeat(i + 1), (i + 1) * BEAT),
        )
      },
      { threshold: 0.35 },
    )
    observer.observe(el)
    return () => {
      observer.disconnect()
      timers.forEach(clearTimeout)
    }
  }, [host, steps])

  return beat
}

/** An orthogonal connector between two cells, in the demo's grid space. Elbowed rather
 *  than diagonal, because that is what the product's router draws. */
function edgePath(a: DemoNode, b: DemoNode): string {
  const CW = 100 / 12
  const RH = 100 / 8
  const cx = (n: DemoNode) => (n.col + (n.span ?? 3) / 2) * CW
  const cy = (n: DemoNode) => (n.row + 0.5) * RH
  const [x1, y1, x2, y2] = [cx(a), cy(a), cx(b), cy(b)]
  if (Math.abs(y1 - y2) < 0.5) return `M ${x1} ${y1} L ${x2} ${y2}`
  const mid = (y1 + y2) / 2
  return `M ${x1} ${y1} L ${x1} ${mid} L ${x2} ${mid} L ${x2} ${y2}`
}

export function DiagramDemo({
  script,
  caption,
}: {
  script: DemoScript
  /** Describes the animation for anyone who cannot see it. */
  caption: string
}) {
  const host = useRef<HTMLDivElement>(null)
  const lastBeat = Math.max(
    ...script.nodes.map((n) => n.beat),
    ...script.edges.map((e) => e.beat),
    script.stages.length,
  )
  const beat = usePlayback(lastBeat, host)
  const byId = new Map(script.nodes.map((n) => [n.id, n]))
  const done = beat >= lastBeat

  return (
    <div className="demo" ref={host} role="img" aria-label={caption}>
      <div className="demo-head" aria-hidden="true">
        <span className="demo-icon">
          <Home size={13} />
        </span>
        <span className="demo-div" />
        <span className="demo-title">{beat >= 2 ? script.title : 'Untitled'}</span>
        {done && (
          <span className="demo-save">
            <span className="demo-save-dot" />
            Saved
          </span>
        )}
        <span className="demo-spacer" />
        <span className="demo-zoom">100%</span>
      </div>

      <div className="demo-body">
        <div className="demo-canvas" aria-hidden="true">
          <div className="demo-frame">
            <span className="demo-frame-title">{beat >= 2 ? script.title : ''}</span>

            <svg className="demo-wires" viewBox="0 0 100 100" preserveAspectRatio="none">
              {script.edges.map((e) => {
                const a = byId.get(e.from)
                const b = byId.get(e.to)
                if (!a || !b) return null
                return (
                  <path
                    key={`${e.from}-${e.to}`}
                    d={edgePath(a, b)}
                    className={`demo-wire${beat >= e.beat ? ' is-in' : ''}${e.added ? ' is-new' : ''}`}
                    vectorEffect="non-scaling-stroke"
                  />
                )
              })}
            </svg>

            {script.nodes.map((n) => (
              <div
                key={n.id}
                className={`demo-node${beat >= n.beat ? ' is-in' : ''}${n.added ? ' is-new' : ''}`}
                style={{
                  left: `${(n.col / 12) * 100}%`,
                  top: `${(n.row / 8) * 100}%`,
                  width: `${((n.span ?? 3) / 12) * 100}%`,
                  ['--node-accent' as string]: n.accent,
                }}
              >
                <span className="demo-node-icon">
                  <Board size={11} />
                </span>
                <span className="demo-node-text">
                  <strong>{n.label}</strong>
                  <span>{n.sub}</span>
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="demo-rail" aria-hidden="true">
          <div className="demo-rail-head">
            <span className="demo-rail-mark">
              <Sparkle size={12} />
            </span>
            <span className="demo-rail-name">
              Canvo AI
              <span>{done ? 'Diagram copilot' : 'Working…'}</span>
            </span>
          </div>

          <div className="demo-log">
            <p className="demo-prompt">{script.prompt}</p>

            {beat > 0 && (
              <div className={`demo-result${done ? '' : ' is-live'}`}>
                <span className="demo-result-icon">
                  <Board size={12} />
                </span>
                <span>
                  <strong>{done ? script.result : 'Working…'}</strong>
                  <span>
                    {done
                      ? `${script.nodes.length} nodes · ${script.edges.length} connections`
                      : script.stages[Math.min(beat, script.stages.length) - 1]}
                  </span>
                </span>
              </div>
            )}

            <ul className="demo-stages">
              {script.stages.map((stage, i) => (
                <li key={stage} className={beat > i ? 'is-done' : beat === i ? 'is-live' : ''}>
                  <span className="demo-stage-dot" />
                  {stage}
                </li>
              ))}
            </ul>
          </div>

          <div className="demo-composer">
            <span>{done ? 'Describe a change…' : 'Describe a system to diagram…'}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
