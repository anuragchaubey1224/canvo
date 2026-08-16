// Mirror of the Python service contract (shared/actions.schema.json).
// Kept intentionally small; a contract test guards drift (PLAN.md §4).

export interface Shape {
  id: string
  type: string // "geo" | "arrow" | ...
  x: number
  y: number
  w?: number
  h?: number
  text?: string | null
  from_id?: string | null
  to_id?: string | null
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
}
