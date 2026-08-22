// Custom tldraw shape: a ROUTED connector (P2 — our own obstacle-avoiding router).
// The server computes orthogonal waypoints around cards and foreign panels; this shape
// renders them as a polyline with rounded bends, an arrowhead, and a label chip pinned
// to the route's longest segment. Trade-off vs tldraw's bound elbow arrows: routes are
// authoritative and never cut through content, but they don't re-route when a card is
// dragged (regenerate for that) — arrows the router can't solve still fall back to
// bound elbow arrows in the apply layer.

import {
  HTMLContainer,
  Polyline2d,
  ShapeUtil,
  T,
  Vec,
  useValue,
  type RecordProps,
  type TLBaseShape,
} from 'tldraw'
import { accent, shapeTheme } from './theme'

export interface ConnectorProps {
  // Waypoints relative to the shape's (x, y), flat [x0,y0,x1,y1,...]
  points: number[]
  accent: string
  label: string
  labelX: number
  labelY: number
}

declare module '@tldraw/tlschema' {
  interface TLGlobalShapePropsMap {
    connector: ConnectorProps
  }
}

export type ConnectorShape = TLBaseShape<'connector', ConnectorProps>

const BEND_RADIUS = 6

function toPairs(flat: number[]): [number, number][] {
  const out: [number, number][] = []
  for (let i = 0; i + 1 < flat.length; i += 2) out.push([flat[i], flat[i + 1]])
  return out
}

// Orthogonal polyline → SVG path with small rounded corners at each bend.
function roundedPath(pts: [number, number][]): string {
  if (pts.length < 2) return ''
  let d = `M ${pts[0][0]} ${pts[0][1]}`
  for (let i = 1; i < pts.length - 1; i++) {
    const [px, py] = pts[i - 1]
    const [cx, cy] = pts[i]
    const [nx, ny] = pts[i + 1]
    const inLen = Math.hypot(cx - px, cy - py)
    const outLen = Math.hypot(nx - cx, ny - cy)
    const r = Math.min(BEND_RADIUS, inLen / 2, outLen / 2)
    const inX = cx - ((cx - px) / (inLen || 1)) * r
    const inY = cy - ((cy - py) / (inLen || 1)) * r
    const outX = cx + ((nx - cx) / (outLen || 1)) * r
    const outY = cy + ((ny - cy) / (outLen || 1)) * r
    d += ` L ${inX} ${inY} Q ${cx} ${cy} ${outX} ${outY}`
  }
  const last = pts[pts.length - 1]
  d += ` L ${last[0]} ${last[1]}`
  return d
}

export class ConnectorUtil extends ShapeUtil<ConnectorShape> {
  static override type = 'connector' as const
  static override props: RecordProps<ConnectorShape> = {
    points: T.arrayOf(T.number),
    accent: T.string,
    label: T.string,
    labelX: T.number,
    labelY: T.number,
  }

  override getDefaultProps(): ConnectorShape['props'] {
    return { points: [0, 0, 100, 0], accent: 'grey', label: '', labelX: 50, labelY: 0 }
  }

  override getGeometry(shape: ConnectorShape) {
    const pts = toPairs(shape.props.points).map(([x, y]) => new Vec(x, y))
    return new Polyline2d({ points: pts.length >= 2 ? pts : [new Vec(0, 0), new Vec(1, 0)] })
  }

  override canResize() {
    return false
  }

  override hideResizeHandles() {
    return true
  }

  override hideRotateHandle() {
    return true
  }

  override component(shape: ConnectorShape) {
    // Not a React class component: tldraw calls `component()` from inside its own stable
    // per-shape function-component wrapper, so this hook runs in a consistent position on
    // every render — the standard tldraw ShapeUtil pattern, safe despite the syntax.
    // oxlint-disable-next-line react/rules-of-hooks
    const dark = useValue('isDark', () => this.editor.user.getIsDarkMode(), [this.editor])
    const t = shapeTheme(dark)
    const a = accent(shape.props.accent, dark)
    const pts = toPairs(shape.props.points)
    if (pts.length < 2) return null

    // Arrowhead aligned with the final segment.
    const [ex, ey] = pts[pts.length - 1]
    const [px, py] = pts[pts.length - 2]
    const angle = (Math.atan2(ey - py, ex - px) * 180) / Math.PI

    const minX = Math.min(...pts.map((p) => p[0])) - 12
    const minY = Math.min(...pts.map((p) => p[1])) - 12
    const w = Math.max(...pts.map((p) => p[0])) - minX + 24
    const h = Math.max(...pts.map((p) => p[1])) - minY + 24

    return (
      <HTMLContainer style={{ pointerEvents: 'none' }}>
        <svg
          width={w}
          height={h}
          viewBox={`${minX} ${minY} ${w} ${h}`}
          style={{ position: 'absolute', left: minX, top: minY, overflow: 'visible' }}
          aria-hidden="true"
        >
          <path
            d={roundedPath(pts)}
            fill="none"
            stroke={a}
            strokeWidth={1.75}
            strokeLinecap="round"
          />
          <g transform={`translate(${ex}, ${ey}) rotate(${angle})`}>
            <path d="M 0 0 L -8 -3.5 L -8 3.5 Z" fill={a} />
          </g>
        </svg>
        {shape.props.label && (
          <div
            style={{
              position: 'absolute',
              left: shape.props.labelX,
              top: shape.props.labelY,
              transform: 'translate(-50%, -50%)',
              background: t.cardBg,
              border: `1px solid ${t.cardBorder}`,
              borderRadius: 4,
              padding: '1px 6px',
              fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
              fontSize: 10,
              fontWeight: 500,
              color: a,
              whiteSpace: 'nowrap',
              lineHeight: 1.4,
            }}
          >
            {shape.props.label}
          </div>
        )}
      </HTMLContainer>
    )
  }

  override getIndicatorPath(shape: ConnectorShape) {
    const pts = toPairs(shape.props.points)
    const path = new Path2D()
    if (pts.length >= 2) {
      path.moveTo(pts[0][0], pts[0][1])
      for (let i = 1; i < pts.length; i++) path.lineTo(pts[i][0], pts[i][1])
    }
    return path
  }
}
