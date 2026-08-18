// Custom tldraw shape: the outer diagram frame (ADR-013).
//
// One titled box holding the whole composition. It is what makes a generated diagram read
// as a finished artefact rather than shapes that happen to sit near each other — and its
// padding is deliberately wide, because the arrow router uses that band as the corridor
// for long cross-panel runs.
//
// Created first (stream order = z-order), so it sits under the panels and cards.

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
import { shapeTheme } from './theme'

export interface FrameProps {
  w: number
  h: number
  title: string
}

declare module '@tldraw/tlschema' {
  interface TLGlobalShapePropsMap {
    frame: FrameProps
  }
}

export type FrameShape = TLBaseShape<'frame', FrameProps>

export class FrameUtil extends ShapeUtil<FrameShape> {
  static override type = 'frame' as const
  static override props: RecordProps<FrameShape> = { w: T.number, h: T.number, title: T.string }

  override getDefaultProps(): FrameShape['props'] {
    return { w: 960, h: 640, title: '' }
  }

  override getGeometry(shape: FrameShape) {
    // Not filled: clicks fall through to the panels and cards inside it.
    return new Rectangle2d({ width: shape.props.w, height: shape.props.h, isFilled: false })
  }

  override onResize(shape: FrameShape, info: TLResizeInfo<FrameShape>) {
    const { scaleX, scaleY } = info
    return {
      ...shape,
      props: {
        ...shape.props,
        w: Math.max(320, shape.props.w * Math.abs(scaleX)),
        h: Math.max(240, shape.props.h * Math.abs(scaleY)),
      },
    }
  }

  override component(shape: FrameShape) {
    const dark = useValue('isDark', () => this.editor.user.getIsDarkMode(), [this.editor])
    const t = shapeTheme(dark)
    const { w, h, title } = shape.props
    return (
      <HTMLContainer style={{ pointerEvents: 'none', width: w, height: h }}>
        <div
          style={{
            width: '100%',
            height: '100%',
            boxSizing: 'border-box',
            background: t.frameFill,
            border: `1px solid ${t.frameBorder}`,
            borderRadius: 18,
            padding: '20px 28px',
            fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
          }}
        >
          {title && (
            <div style={{ fontSize: 20, fontWeight: 650, color: t.text, letterSpacing: '-0.01em' }}>
              {title}
            </div>
          )}
        </div>
      </HTMLContainer>
    )
  }

  override getIndicatorPath(shape: FrameShape) {
    const path = new Path2D()
    path.roundRect(0, 0, shape.props.w, shape.props.h, 18)
    return path
  }
}
