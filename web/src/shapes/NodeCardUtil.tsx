// Custom tldraw shape: the Eraser-style node card (ADR-013).
// One shape type, three visual modes by kind:
//   - decision  → diamond with centered label
//   - datastore → cylinder with title + subtitle
//   - default   → card: accent-tinted icon box, semibold title, muted subtitle
// Cards are ordinary tldraw shapes — selectable, movable, resizable, serialized in
// snapshots, and valid arrow-binding targets.

import {
  HTMLContainer,
  Rectangle2d,
  ShapeUtil,
  T,
  useValue,
  type RecordProps,
  type TLBaseShape,
  type TLResizeInfo,
} from 'tldraw'
import { iconFor } from './iconset'
import { Icon } from './icons'
import { accent, shapeTheme } from './theme'

export interface NodeCardProps {
  w: number
  h: number
  title: string
  subtitle: string
  kind: string
  accent: string
  icon: string
}

// Register the shape in tldraw's global shape map (tldraw 5 custom-shape mechanism) —
// this is what makes NodeCardShape a valid TLShape for the editor's typed APIs.
declare module '@tldraw/tlschema' {
  interface TLGlobalShapePropsMap {
    'node-card': NodeCardProps
  }
}

export type NodeCardShape = TLBaseShape<'node-card', NodeCardProps>

const FONT = 'Inter, system-ui, -apple-system, sans-serif'

export class NodeCardUtil extends ShapeUtil<NodeCardShape> {
  static override type = 'node-card' as const
  static override props: RecordProps<NodeCardShape> = {
    w: T.number,
    h: T.number,
    title: T.string,
    subtitle: T.string,
    kind: T.string,
    accent: T.string,
    icon: T.string,
  }

  override getDefaultProps(): NodeCardShape['props'] {
    return { w: 200, h: 64, title: 'Node', subtitle: '', kind: 'service', accent: 'grey', icon: '' }
  }

  override getGeometry(shape: NodeCardShape) {
    return new Rectangle2d({ width: shape.props.w, height: shape.props.h, isFilled: true })
  }

  override onResize(shape: NodeCardShape, info: TLResizeInfo<NodeCardShape>) {
    const { scaleX, scaleY } = info
    return {
      ...shape,
      props: {
        ...shape.props,
        w: Math.max(120, shape.props.w * Math.abs(scaleX)),
        h: Math.max(48, shape.props.h * Math.abs(scaleY)),
      },
    }
  }

  override component(shape: NodeCardShape) {
    // Not a React class component: tldraw calls `component()` from inside its own stable
    // per-shape function-component wrapper, so this hook runs in a consistent position on
    // every render — the standard tldraw ShapeUtil pattern, safe despite the syntax.
    // oxlint-disable-next-line react/rules-of-hooks
    const dark = useValue('isDark', () => this.editor.user.getIsDarkMode(), [this.editor])
    const t = shapeTheme(dark)
    const a = accent(shape.props.accent, dark)
    const { w, h, title, subtitle, kind } = shape.props

    if (kind === 'decision') {
      return (
        <HTMLContainer style={{ pointerEvents: 'none', width: w, height: h }}>
          <svg width={w} height={h} style={{ position: 'absolute', inset: 0 }} aria-hidden="true">
            <polygon
              points={`${w / 2},1 ${w - 1},${h / 2} ${w / 2},${h - 1} 1,${h / 2}`}
              fill={t.cardBg}
              stroke={a}
              strokeWidth={1.25}
            />
          </svg>
          <div
            style={{
              position: 'absolute',
              inset: '0 18%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              fontFamily: FONT,
              fontSize: 12,
              fontWeight: 600,
              lineHeight: 1.25,
              color: t.text,
            }}
          >
            {title}
          </div>
        </HTMLContainer>
      )
    }

    if (kind === 'datastore') {
      const cap = Math.min(16, h * 0.18) // cylinder cap depth
      return (
        <HTMLContainer style={{ pointerEvents: 'none', width: w, height: h }}>
          <svg width={w} height={h} style={{ position: 'absolute', inset: 0 }} aria-hidden="true">
            <path
              d={`M1 ${cap} A ${w / 2 - 1} ${cap - 1} 0 0 1 ${w - 1} ${cap} V ${h - cap} A ${w / 2 - 1} ${cap - 1} 0 0 1 1 ${h - cap} Z`}
              fill={t.cardBg}
              stroke={a}
              strokeWidth={1.25}
            />
            <ellipse
              cx={w / 2}
              cy={cap}
              rx={w / 2 - 1}
              ry={cap - 1}
              fill={t.cardBg}
              stroke={a}
              strokeWidth={1.25}
            />
          </svg>
          <div
            style={{
              position: 'absolute',
              inset: `${cap + 4}px 12px 6px`,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 2,
              textAlign: 'center',
              fontFamily: FONT,
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 600, color: t.text, lineHeight: 1.2 }}>
              {title}
            </div>
            {subtitle && (
              <div style={{ fontSize: 11, color: t.textMuted, lineHeight: 1.2 }}>{subtitle}</div>
            )}
          </div>
        </HTMLContainer>
      )
    }

    // default: card with icon box + title + subtitle
    return (
      <HTMLContainer style={{ pointerEvents: 'none', width: w, height: h }}>
        <div
          style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '0 14px',
            boxSizing: 'border-box',
            background: t.cardBg,
            border: `1px solid ${t.cardBorder}`,
            borderRadius: 10,
            fontFamily: FONT,
          }}
        >
          <div
            style={{
              flex: 'none',
              width: 32,
              height: 32,
              display: 'grid',
              placeItems: 'center',
              borderRadius: 8,
              background: t.iconBg(a),
            }}
          >
            <Icon name={iconFor(shape.props.icon, kind)} color={a} />
          </div>
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: 13,
                fontWeight: 600,
                color: t.text,
                lineHeight: 1.25,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {title}
            </div>
            {subtitle && (
              <div
                style={{
                  fontSize: 11,
                  color: t.textMuted,
                  lineHeight: 1.3,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {subtitle}
              </div>
            )}
          </div>
        </div>
      </HTMLContainer>
    )
  }

  override getIndicatorPath(shape: NodeCardShape) {
    const { w, h, kind } = shape.props
    const path = new Path2D()
    if (kind === 'decision') {
      path.moveTo(w / 2, 0)
      path.lineTo(w, h / 2)
      path.lineTo(w / 2, h)
      path.lineTo(0, h / 2)
      path.closePath()
    } else {
      path.roundRect(0, 0, w, h, kind === 'datastore' ? 4 : 10)
    }
    return path
  }
}
