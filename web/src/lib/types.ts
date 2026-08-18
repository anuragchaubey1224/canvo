// Mirror of the Python service contract (shared/actions.schema.json).
// Kept intentionally small; a contract test guards drift (PLAN.md §4).

export interface Shape {
  id: string
  type: string // "geo" | "arrow" | "container" | "frame" | ...
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
  enable_spec?: boolean
}

// Emitted once by the Spec Writer (`event: spec`) — what the service understood from a
// vague request, and everything it had to assume to complete the picture. Showing the
// assumptions is the point: invented detail stays visible instead of silently landing
// in the diagram.
export interface SpecEvent {
  title: string | null
  diagram_type: string | null
  components: string[]
  flow_steps: number
  phases: string[]
  assumptions: string[]
  raw: string
}

export interface PlanIssue {
  kind: string // "single_branch" | "missing_components" | "thin_coverage" | ...
  severity: string // "error" | "warning"
  message: string
}

// Emitted once by the Planner (`event: plan`) — the graph it produced plus what the
// deterministic validator repaired or flagged.
export interface PlanEvent {
  nodes: number
  edges: number
  groups: number
  issues: PlanIssue[]
  fixes: string[]
  repaired: boolean
  // Non-empty when a stage failed and something cheaper drew the diagram. Surfaced rather
  // than hidden: a silent fallback looks identical to success until you read the picture.
  degraded: string
  // A follow-up prompt edits the diagram already on screen instead of drawing a new one.
  // Which path ran is shown, because getting it wrong is the failure the user notices.
  intent: 'create' | 'edit' | 'replace'
  applied: string[]
  rejected: string[]
  summary: string
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
