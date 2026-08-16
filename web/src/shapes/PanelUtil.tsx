// Custom tldraw shape: a group panel (Eraser-style swimlane container) — translucent
// accent-tinted fill, hairline accent border, small semibold title top-left. Drawn
// before its member cards (stream order = z-order), so it sits underneath them.

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
import { accent, shapeTheme } from './theme'

export interface PanelProps {
  w: number
  h: number
  title: string
  accent: string
}

// Register in tldraw's global shape map (see NodeCardUtil for the pattern).
declare module '@tldraw/tlschema' {
  interface TLGlobalShapePropsMap {
    panel: PanelProps
  }
}

export type PanelShape = TLBaseShape<'panel', PanelProps>

export class PanelUtil extends ShapeUtil<PanelShape> {
  static override type = 'panel' as const
  static override props: RecordProps<PanelShape> = {
    w: T.number,
    h: T.number,
    title: T.string,
    accent: T.string,
  }

  override getDefaultProps(): PanelShape['props'] {
    return { w: 480, h: 320, title: 'Group', accent: 'grey' }
  }

  override getGeometry(shape: PanelShape) {
    return new Rectangle2d({ width: shape.props.w, height: shape.props.h, isFilled: true })
  }

  override onResize(shape: PanelShape, info: TLResizeInfo<PanelShape>) {
    const { scaleX, scaleY } = info
    return {
      ...shape,
      props: {
        ...shape.props,
        w: Math.max(160, shape.props.w * Math.abs(scaleX)),
        h: Math.max(120, shape.props.h * Math.abs(scaleY)),
      },
    }
  }

  override component(shape: PanelShape) {
    const dark = useValue('isDark', () => this.editor.user.getIsDarkMode(), [this.editor])
    const t = shapeTheme(dark)
    const a = accent(shape.props.accent, dark)
    return (
      <HTMLContainer
        style={{ pointerEvents: 'none', width: shape.props.w, height: shape.props.h }}
      >
        <div
          style={{
            width: '100%',
            height: '100%',
            boxSizing: 'border-box',
            background: t.panelFill(a),
            border: `1px solid ${t.panelBorder(a)}`,
            borderRadius: 14,
            padding: '12px 16px',
            fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
          }}
        >
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 12,
              fontWeight: 600,
              letterSpacing: '0.01em',
              color: a,
              lineHeight: 1.2,
            }}
          >
            <span
              style={{ width: 7, height: 7, borderRadius: 2, background: a, opacity: 0.9 }}
            />
            {shape.props.title}
          </div>
        </div>
      </HTMLContainer>
    )
  }

  override getIndicatorPath(shape: PanelShape) {
    const path = new Path2D()
    path.roundRect(0, 0, shape.props.w, shape.props.h, 14)
    return path
  }
}
