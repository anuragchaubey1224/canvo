// The ShapeRegistry (ADR-013): every custom canvas shape registers here, and the
// tldraw editor receives them all via `shapeUtils`. Adding a new shape = one Util
// file + one entry — never a contract or engine change.

import { ConnectorUtil } from './ConnectorUtil'
import { FrameUtil } from './FrameUtil'
import { NodeCardUtil } from './NodeCardUtil'
import { PanelUtil } from './PanelUtil'

export const customShapeUtils = [FrameUtil, NodeCardUtil, PanelUtil, ConnectorUtil]
export { ConnectorUtil, FrameUtil, NodeCardUtil, PanelUtil }
