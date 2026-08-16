# Canvo — Spec-to-Diagram Agentic Canvas

> Turn your **specs, docs, and ideas** into live, editable diagrams. A multi-tool agent
> (Router → Planner → Drawer → Critic) on a **custom graph engine** reasons over real inputs — a
> PRD, an OpenAPI spec, a SQL schema, code, or a plain description — draws on an infinite canvas,
> and **self-corrects** with vision.

**Status:** 🚧 taking shape — the agent runs end-to-end, wired to a live tldraw canvas with
persistence. Real paths: **SQL → ERD** and **OpenAPI → API surface** (deterministic), and
**freeform text → diagram** via an **LLM planner** (tool-calling / structured output). The
**Critic now self-corrects** — a deterministic geometry pass plus a vision pass (an LLM looks at
a rendered PNG of the diagram) drive a bounded refine loop that widens crowded layouts, streamed
live so it's observable. Richer node/group styling and RAG are next. 26 passing tests, ruff/mypy
clean. Full plan: [`PLAN.md`](./PLAN.md).

---

## Why this exists

A portfolio proof-of-work aimed at **AI-Engineer · Agentic-AI · Python-backend** roles, built to
three rules: (1) proper Python agentic AI, (2) clear advantage across those roles, (3) a **real
product people can actually use** — deployed, not a demo script. See [`PLAN.md` §3](./PLAN.md) for
the feature ↔ requirement map.

## Architecture (hybrid — thin canvas, deep Python brain)

```
tldraw client (React/TS)  ──POST /agent/stream (SSE)──▶  Python agent-service (FastAPI, async)
  input tray + canvas                                     custom engine: Router→Planner→Drawer→Critic
  (applies streamed actions)                              tools: parse OpenAPI/SQL/code · RAG (pgvector)
        ▲                                                 Claude tool-calling · own tracing · guardrails
        └──────────── streamed AgentAction[] ◀────────────┘  auth · quotas · MCP · BYOK
                                                          Supabase (Postgres + pgvector)
```

- **`agent/`** — Python FastAPI service on a custom graph engine (**where the engineering lives**). Runnable now.
- **`web/`** — tldraw canvas client (thin; built directly on the tldraw SDK, our own action-apply layer).
- **`shared/`** — the client↔server contract (one schema → Zod + Pydantic).

## Quickstart (agent service)

```bash
cd agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add ANTHROPIC_API_KEY when wiring the LLM
uvicorn app.main:app --reload   # http://127.0.0.1:8000

# smoke test — SQL schema → ERD:
curl -N -X POST http://127.0.0.1:8000/agent/stream \
  -H 'content-type: application/json' \
  -d '{"message":"","payload":"CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255)); CREATE TABLE orders (id SERIAL PRIMARY KEY, user_id INT REFERENCES users(id));"}'

# run the tests:
python -m pytest
```

You'll see `AgentAction` events stream back: a table box per table (with PK/FK markers) plus a bound
arrow per foreign-key relation.

## Roadmap

Phased plan (v0 deployed vertical slice → v1 depth → v2 stretch), eval design, backend pillar, and
resume framing all live in [`PLAN.md`](./PLAN.md).

## Tech stack

Python · FastAPI · custom graph engine · Claude · pgvector · tldraw/React-TS · Supabase · Docker · GitHub Actions · MCP
