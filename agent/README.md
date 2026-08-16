# Canvo Agent Service

Python + FastAPI service that plans, draws, and self-corrects diagrams for the tldraw canvas
client. This is the "brain" of Canvo — orchestrated by **our own graph engine**
(`app/graph/engine.py`), no framework.

## Layout

```
agent/
├── app/
│   ├── main.py           # FastAPI: /health, /agent/stream (SSE)
│   ├── schema.py         # Pydantic contract: AgentInput, CanvasContext, AgentAction
│   ├── llm.py            # provider abstraction (Anthropic / OpenRouter / …) + BYOK
│   ├── guardrails.py     # cost/iteration caps (stubs; real safety layer in v1)
│   ├── tools/
│   │   ├── parse_sql.py      # SQL DDL → schema (tables, columns, relations)
│   │   └── parse_openapi.py  # OpenAPI/Swagger (JSON/YAML) → grouped API surface
│   └── graph/
│       ├── engine.py        # our own graph engine (nodes, edges, conditional loop, streaming)
│       ├── state.py         # AgentState (the run state the engine merges into)
│       ├── nodes.py         # router / planner / drawer / critic
│       ├── planner_llm.py   # freeform text → typed DiagramPlan (structured output)
│       ├── layout.py        # deterministic layout (parsed input → actions), gap_scale-tunable
│       ├── critique.py      # geometry critic — overlaps / dangling arrows (deterministic)
│       ├── render.py        # rasterize actions → PNG for the vision critic (Pillow)
│       ├── critic_vision.py # vision critic — an LLM looks at the PNG and judges layout
│       └── build.py         # graph wiring on engine.py + bounded refine loop
├── tests/                # pytest: parser + graph
├── requirements.txt · requirements-dev.txt · pytest.ini
└── .env.example
```

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

- `GET  /health` → service status
- `POST /agent/stream` → runs the Planner→Drawer→Critic graph, streams `AgentAction` events (SSE)
- `POST /sessions` → create a session (persistence)
- `GET  /sessions/{id}/snapshot` · `PUT /sessions/{id}/snapshot` → load / save the tldraw snapshot

Persistence uses SQLAlchemy (async) on SQLite for dev (`canvo.db`); set `DATABASE_URL` to a
Postgres URL for prod. Models/engine/repository live in `app/db/`.

## What works vs what's a stub

- ✅ **SQL schema → ERD** — real and deterministic (no LLM). Router detects SQL, `parse_sql` builds a
  structured schema, and `layout.py` emits table boxes + bound relation arrows. Covered by `tests/`.
- ✅ **OpenAPI/Swagger → API surface** — deterministic (no LLM). `parse_openapi` (JSON or YAML) groups
  operations by tag, and `layout.py` emits a root node + per-group endpoint boxes with arrows.
- ✅ **Freeform text → diagram** — LLM planner (`planner_llm.py`) uses tool-calling / structured
  output to turn a description into a typed node/edge graph, then `build_graph_actions` lays it out.
  Needs an LLM key (`OPENROUTER_API_KEY` / `ANTHROPIC_API_KEY`); falls back to a stub without one.
- ✅ **Critic — self-correction (two passes).** A deterministic **geometry** pass (`critique.py`)
  flags overlapping/crowded boxes and dangling arrows; a best-effort **vision** pass
  (`render.py` → PNG → `critic_vision.py`) has an LLM *look at* the rendered diagram and judge
  its layout. When a spacing-fixable problem is found the graph loops back to the Drawer with a
  wider `gap_scale` (bounded, `MAX_ITERATIONS`), and each pass streams a `critique` SSE event so
  the self-correction is observable. Geometry is covered by `tests/`; vision degrades gracefully
  without a key.

## Test

```bash
pip install -r requirements-dev.txt
python -m pytest
```
