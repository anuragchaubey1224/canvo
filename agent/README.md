# Canvo Agent Service

Python + FastAPI + LangGraph service that plans, draws, and self-corrects diagrams for the
tldraw canvas client. This is the "brain" of Canvo.

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
│       ├── state.py      # AgentState (LangGraph state)
│       ├── nodes.py      # router / planner / drawer / critic
│       ├── layout.py     # deterministic ERD layout (parsed schema → actions)
│       └── build.py      # StateGraph wiring + bounded refine loop
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
- 🚧 **Critic** — always "no issues" for now; vision-based self-correction lands in v1 (`PLAN.md` §5).

## Test

```bash
pip install -r requirements-dev.txt
python -m pytest
```
