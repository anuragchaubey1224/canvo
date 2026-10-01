# 01 — System Architecture

## Shape of the system: thin canvas, deep Python brain

Canvo is a **hybrid** architecture. The browser runs a deliberately thin tldraw client; every
piece of intelligence — parsing, planning, layout, drawing, self-correction, persistence,
auth, quotas — lives in a single async Python service. This is a deliberate inversion of most
canvas products (which put logic in the client): it keeps the client replaceable, makes the
agent testable without a browser, and concentrates the engineering where Python is strongest.

```
┌────────────────────────────────────────────────────────────────────────┐
│ web/ — tldraw client (React 19 + TS, Vite)                    [THIN]  │
│                                                                        │
│  Input tray (paste PRD / OpenAPI / SQL / code / text)                  │
│  Chat panel + Critic strip (streams the agent's self-correction)       │
│  tldraw canvas — applies streamed AgentActions live                    │
│  Session autosave / restore (snapshot API)                             │
└──────────────┬──────────────────────────────────────▲──────────────────┘
               │ POST /agent/stream (SSE)             │ AgentAction[] +
               │ AgentInput {message, payload,        │ critique events
               │             canvas_context}          │ (typed, streamed)
               ▼                                      │
┌────────────────────────────────────────────────────────────────────────┐
│ agent/ — Python 3.11+ FastAPI (async)                        [DEEP]   │
│                                                                        │
│  ┌──────── custom graph engine (app/graph/engine.py) ────────────┐    │
│  │                                                                │    │
│  │   Router ──▶ Planner ──▶ Drawer ──▶ Critic ──▶ done            │    │
│  │                            ▲            │                      │    │
│  │                            └── refine ──┘  (bounded loop,      │    │
│  │                                gap_scale ×1.5, MAX_ITER=3)     │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                        │
│  Tools: parse_sql · parse_openapi · (parse_code, RAG retrieve — v1)    │
│  LLM layer: provider abstraction (Anthropic / OpenRouter / BYOK)       │
│  Critic: deterministic geometry + vision (Pillow render → LLM judge)   │
│  Guardrails: iteration caps, cost caps, input sanitization             │
│  Persistence: SQLAlchemy async → SQLite (dev) / Postgres (prod)        │
│  Auth & quotas: session cookies (Argon2id), per-account allowance         │
└──────────────┬─────────────────────────────────────────────────────────┘
               ▼
        Postgres (+ pgvector for RAG, v1) — Supabase or any managed PG
```

## The contract (the most important interface in the repo)

One schema, defined once, mirrored twice:

- Source of truth: `shared/actions.schema.json`
- Server types: Pydantic models in `agent/app/schema.py`
- Client types: TypeScript in `web/src/lib/types.ts`

**Request** — `AgentInput`:
```
{ message: string,            // user's instruction ("draw a JWT auth flow")
  input_kind?: string,        // hint: sql | openapi | text | code (router can override)
  payload?: string,           // the raw material (DDL, spec, PRD text…)
  canvas_context?: {...} }    // focused shapes / viewport / screenshot (for edits)
```

**Response** — a Server-Sent Events stream:
- `event: action` → one `AgentAction` per event (`create_shape`, `create_arrow`,
  `update_shape`, `delete_shape`, `create_group`…). The client applies each action as it
  arrives — the diagram draws itself progressively.
- `event: critique` → one per critic pass (geometry / vision), so the UI can show the
  self-correction visibly.
- `event: done` / `event: error` → terminal.

**Shape flexibility (ADR-013):** `create_shape` carries an open-set semantic `kind`
(`service`, `datastore`, `decision`, `queue`, …) plus generic props (`title`, `subtitle`,
`icon`, `color`). The client resolves `kind` through a **ShapeRegistry** — registered kinds
render as custom tldraw `ShapeUtil`s (rich node cards, containers, diamonds); unknown kinds
fall back to a labeled geo box. Adding a brand-new shape is therefore a local change (one
client renderer + an optional server layout spec), never a contract or engine change. Agent
shapes are ordinary tldraw shapes — users can edit them, and can also draw anything themselves
with the full tldraw toolset.

Rules for evolving the contract:
1. **Additive changes only** within a major version (new optional fields, new action types the
   client can ignore). Breaking changes require bumping a `version` field in the stream preamble.
2. Any change touches all three files (JSON schema, Pydantic, TS) in the **same commit**, with a
   test on the server side and a type-check on the client side.

## The agent graph (custom engine — no framework)

`app/graph/engine.py` (~110 lines) is our own orchestrator: nodes, edges, one conditional
edge for the refine loop, sync + async execution, `astream` yielding `(node, update)` deltas,
and a `_MAX_STEPS=64` safety cap. We dropped LangGraph deliberately (see ADR-002).

| Node | Responsibility | LLM? |
|---|---|---|
| **Router** | Classify the input (SQL / OpenAPI / code / freeform), pick the pipeline | No (heuristics; LLM fallback later) |
| **Planner** | Produce a typed `DiagramPlan` (nodes, edges, groups, kinds) | Only for freeform text — structured output via tool-calling. Deterministic inputs go through parsers instead |
| **Drawer** | `DiagramPlan` → concrete `AgentAction[]` via the layout engine (`layout.py`), honoring `gap_scale` | No |
| **Critic** | Two passes: deterministic geometry (`critique.py` — overlaps, dangling arrows) and best-effort vision (`render.py` rasterizes actions → PNG, `critic_vision.py` has an LLM judge it). On a spacing-fixable issue → loop back to Drawer with wider `gap_scale` | Vision pass only, degradable |

Design invariants:
- **The loop is bounded** (`MAX_ITERATIONS=3`) and **cheap-first**: geometry (free) runs before
  vision (one small multimodal call).
- **Every node is a pure-ish function over `AgentState`** — the engine merges returned deltas.
  This keeps nodes unit-testable without the engine and the engine testable with fake nodes.
- **Everything observable**: the stream exposes each node's output; our own lightweight tracing
  (per-node timings, token counts) lands in v1.

## Data model (current + planned)

| Table | Status | Purpose |
|---|---|---|
| `sessions` | ✅ | A canvas file; owns a tldraw snapshot (JSON) |
| `users` | P3 | Supabase-auth-backed identity; quota counters |
| `share_links` | P3 | Signed read-only tokens onto a session snapshot |
| `patterns` (+pgvector) | v1 | Curated diagram patterns for RAG retrieval |
| `generations` | P3 | Audit/metering: input kind, model, tokens, cost, critic iterations |

Migrations: **Alembic** from the moment we point at a real Postgres (P3). Until then SQLite
dev DB is disposable.

## Request lifecycles

**Generate (happy path, freeform text):**
client → `POST /agent/stream` → Router(text) → Planner (LLM, structured output) → Drawer
(layout → actions, streamed as they're built) → Critic geometry pass → *(if crowded)* Drawer
again with `gap_scale=1.5` → Critic clean → `done`. Client has been applying actions the whole
time; the refine pass streams `update_shape` actions that visibly nudge the layout.

**Generate (SQL):** identical, but Planner is replaced by `parse_sql` — no tokens spent.

**Edit (v1):** same endpoint; `canvas_context` carries focused-shape ids + a viewport
screenshot; Planner receives the *existing* plan and emits a delta plan; Drawer diffs into
`update/delete/create` actions.

**Persistence:** client debounces tldraw store changes → `PUT /sessions/{id}/snapshot`.
Restore on load via `GET`. Server-side the snapshot is an opaque JSON blob (we do not parse
tldraw internals server-side — the *actions* contract is our semantic layer).

## Scaling posture

Single stateless FastAPI container + managed Postgres serves us far beyond launch scale
(SSE streams are I/O-bound; async handles thousands of concurrent streams per small instance).
Scale path when needed: horizontal replicas behind the platform LB (no sticky sessions
required — streams are single-request), then split the vision-render path into a worker queue
if Pillow CPU ever matters. Details and cost in [07-deployment.md](./07-deployment.md).
