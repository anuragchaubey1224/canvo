# Canvo — Spec-to-Diagram Agentic Canvas

> Turn your **specs, docs, and ideas** into live, editable diagrams. A multi-tool agent
> (Router → Editor → Specifier → Planner → Drawer → Critic) on a **custom graph engine** reasons over real inputs — a
> PRD, an OpenAPI spec, a SQL schema, code, or a plain description — draws on an infinite canvas,
> and **self-corrects** with vision.

**Status:** 🚧 feature-rich, not yet deployed. Works locally end to end: **SQL → ERD** and
**OpenAPI → API surface** (deterministic, zero tokens), **freeform text → diagram** (Spec Writer →
planner → validator), and **conversational editing** ("add a rate limiter" edits the diagram
instead of redrawing it). A **self-correcting Critic** (geometry + vision) drives a bounded refine
loop. Accounts (Argon2id, session cookies), password reset, generation quotas, a per-run cost cap
and a run ledger are in; a Tier 1 eval set runs in CI. ~220 tests, ruff/mypy clean. Next:
[`PLAN-next.md`](./PLAN-next.md). Design docs: [`docs/`](./docs/README.md).

---

## Why this exists

A portfolio proof-of-work aimed at **AI-Engineer · Agentic-AI · Python-backend** roles, built to
three rules: (1) proper Python agentic AI, (2) clear advantage across those roles, (3) a **real
product people can actually use** — deployed, not a demo script. See [`PLAN.md` §3](./PLAN.md) for
the feature ↔ requirement map.

## Architecture (hybrid — thin canvas, deep Python brain)

```
tldraw client (React/TS)  ──POST /agent/stream (SSE)──▶  Python agent-service (FastAPI, async)
  input tray + canvas                                     custom engine: Router→Editor→Spec→Plan→Draw→Critic
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
cp .env.example .env            # add OPENROUTER_API_KEY (or ANTHROPIC_API_KEY) for the LLM paths
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

Python · FastAPI · custom graph engine · OpenRouter/Claude · tldraw/React-TS · SQLAlchemy+Alembic · Docker · GitHub Actions  (planned: pgvector · MCP · Supabase/Render deploy)
