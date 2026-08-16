// Mirror of the Python service contract (shared/actions.schema.json).
// Kept intentionally small; a contract test guards drift (PLAN.md §4).

export interface Shape {
  id: string
  type: string // "geo" | "arrow" | "container" | ...
  x: number
  y: number
  w?: number
  h?: number
  text?: string | null
  from_id?: string | null
  to_id?: string | null
  // Semantic styling (ADR-013: open set — unknown kinds fall back to a plain box).
  kind?: string | null // "service" | "datastore" | "decision" | ...
  subtitle?: string | null
  color?: string | null // tldraw color token
  parent_id?: string | null // container membership
  icon?: string | null // icon name (open set; falls back to the kind's default)
  // Routed arrows: absolute orthogonal waypoints [x0,y0,...] + label chip anchor.
  points?: number[] | null
  label_x?: number | null
  label_y?: number | null
}

export interface AgentAction {
  type: 'create' | 'update' | 'delete'
  shape?: Shape | null
  shape_id?: string | null
}

export interface AgentInput {
  message: string
  payload?: string | null
  input_kind?: string | null
  session_id?: string
  enable_vision?: boolean
}

export interface CritiqueIssue {
  kind: string // "overlap" | "dangling_arrow" | "vision:crowding" | ...
  severity: string // "error" | "warning"
  message: string
  shape_ids: string[]
}

// Emitted once per Critic pass over SSE (`event: critique`) — the self-correction trace.
export interface CritiqueEvent {
  pass: number
  has_issues: boolean
  needs_refine: boolean
  source: string // "geometry" | "geometry+vision"
  summary: string
  gap_scale: number
  issue_count: number
  issues: CritiqueIssue[]
}
