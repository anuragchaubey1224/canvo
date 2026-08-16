# 03 — Folder Structure

## Principles

1. **Two apps, one contract.** `agent/` (Python brain) and `web/` (thin canvas) meet only at
   `shared/actions.schema.json`. Nothing else crosses the boundary.
2. **Feature code goes where the reasoning lives** — almost always `agent/app/`. If you're
   about to add logic to `web/`, first ask whether it belongs in an `AgentAction` instead.
3. **Flat until it hurts.** We add subpackages when a module family exceeds ~4 files, not before.

## Current layout (as of today — everything here exists and runs)

```
erasorAdvanced/
├── docs/                       # ← this documentation set (source of truth for decisions)
├── PLAN.md                     # historical solidified plan v3 (superseded by docs/, kept for context)
├── README.md
├── docker-compose.yml          # agent + (optional) postgres, one-command local stack
│
├── shared/
│   ├── actions.schema.json     # THE contract — AgentInput / AgentAction (source of truth)
│   └── README.md
│
├── agent/                      # Python FastAPI service — the product's brain
│   ├── app/
│   │   ├── main.py             # FastAPI app: /health, /agent/stream (SSE), /sessions*
│   │   ├── schema.py           # Pydantic contract mirror: AgentInput, CanvasContext, AgentAction
│   │   ├── llm.py              # provider abstraction (Anthropic/OpenRouter/BYOK), build_chat_model
│   │   ├── guardrails.py       # cost/iteration caps (stubs → real safety layer in v1)
│   │   ├── graph/              # the agent itself
│   │   │   ├── engine.py       # OUR graph engine: nodes/edges/conditional loop/astream
│   │   │   ├── state.py        # AgentState merged by the engine
│   │   │   ├── nodes.py        # router / planner / drawer / critic node functions
│   │   │   ├── build.py        # graph wiring + bounded refine loop
│   │   │   ├── planner_llm.py  # freeform text → typed DiagramPlan (structured output)
│   │   │   ├── layout.py       # deterministic layout builders (gap_scale-tunable)
│   │   │   ├── critique.py     # geometry critic (overlaps, dangling arrows)
│   │   │   ├── render.py       # actions → PNG (Pillow) for the vision critic
│   │   │   └── critic_vision.py# vision critic (LLM judges the rendered PNG)
│   │   ├── tools/              # input parsers (deterministic, no LLM)
│   │   │   ├── parse_sql.py    # SQL DDL → tables/columns/relations
│   │   │   └── parse_openapi.py# OpenAPI JSON/YAML → grouped API surface
│   │   └── db/                 # persistence
│   │       ├── engine.py       # async engine/session factory (SQLite dev / DATABASE_URL prod)
│   │       ├── models.py       # SQLAlchemy models (sessions/snapshots)
│   │       └── repo.py         # repository layer (no ORM leakage into routes)
│   ├── tests/                  # pytest — parsers, graph paths, critic, refine loop, db
│   ├── pyproject.toml          # ruff + mypy config
│   ├── requirements.txt · requirements-dev.txt · pytest.ini
│   ├── Dockerfile · .dockerignore
│   └── .env.example            # LLM keys/model, DATABASE_URL (never commit .env)
│
├── web/                        # tldraw client — thin by policy
│   ├── src/
│   │   ├── App.tsx             # shell: input tray, chat/critic strip, canvas
│   │   ├── index.css           # design tokens (light+dark) + components
│   │   ├── lib/
│   │   │   ├── types.ts        # TS mirror of the contract
│   │   │   ├── transport.ts    # SSE client for /agent/stream
│   │   │   ├── applyActions.ts # AgentAction → tldraw editor calls (the ~50-line ownership layer)
│   │   │   ├── api.ts          # sessions/snapshot REST calls
│   │   │   └── session.ts      # autosave/restore glue
│   │   └── main.tsx
│   ├── vite.config.ts · tsconfig*.json · package.json
│   └── public/
│
└── .github/
    └── ci.yml.pending          # CI workflow, parked until gh token has `workflow` scope
```

## Target layout (where new roadmap code goes — do not pre-create empty dirs)

```
agent/app/
├── api/                        # (P3) split main.py when routes > ~5: agent.py, sessions.py, auth.py, share.py
├── auth/                       # (P3) Supabase JWT verification middleware, quota enforcement
├── tracing/                    # (v1) our own per-node tracing: span model, decorator, /traces endpoint
├── rag/                        # (v1) pattern library: embeddings, pgvector queries, seed data
├── tools/
│   ├── parse_code.py           # (v1) code → modules/calls graph
│   └── emit_mermaid.py         # (P4) DiagramPlan → Mermaid text (export / diagram-as-code)
├── evals/                      # (v1) eval harness: golden inputs, LLM-as-judge, before/after-critic table
└── db/
    └── migrations/             # (P3) Alembic

web/src/
├── components/                 # split App.tsx when it exceeds ~400 lines: InputTray, CriticStrip, FileList…
├── shapes/                     # (P2) custom tldraw shape utils — node cards (icon+title+subtitle), diamonds
└── lib/                        # stays the integration layer; no business logic
```

## Placement rules (quick reference)

| You are adding… | It goes in… |
|---|---|
| A new input type (e.g. Terraform, Dockerfile) | `agent/app/tools/parse_*.py` + router branch + layout builder + tests |
| A new action type | `shared/actions.schema.json` + `schema.py` + `types.ts` + `applyActions.ts` — one commit |
| A new agent capability (edit, RAG) | `agent/app/graph/` (node or node change) + `build.py` wiring |
| Layout/visual-quality logic | `agent/app/graph/layout.py` (server), **never** client-side positioning |
| A new API route | `agent/app/main.py` (until P3 split) + repo method if it touches the DB |
| UI polish | `web/src/` — tokens first (`index.css`), then components |
| A one-off script/experiment | your scratch space — **not** the repo; promote only what ships |
