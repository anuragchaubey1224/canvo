# Canvo — Spec-to-Diagram Agentic Canvas

> Turn your **specs, docs, and ideas** into live, editable diagrams. A multi-tool **LangGraph**
> agent (Router → Planner → Drawer → Critic) powered by **Claude** reasons over real inputs — a
> PRD, an OpenAPI spec, a SQL schema, code, or a plain description — draws on an infinite canvas,
> and **self-corrects** with vision.

**Status:** 🚧 Phase 0 (scaffold) — the agent service runs end-to-end with stub nodes. Real tools,
RAG, the canvas client, and the production backend land next. Full plan: [`PLAN.md`](./PLAN.md).

---

## Why this exists

A portfolio proof-of-work aimed at **AI-Engineer · Agentic-AI · Python-backend** roles, built to
three rules: (1) proper Python agentic AI, (2) clear advantage across those roles, (3) a **real
product people can actually use** — deployed, not a demo script. See [`PLAN.md` §3](./PLAN.md) for
the feature ↔ requirement map.

## Architecture (hybrid — thin canvas, deep Python brain)

```
tldraw client (React/TS)  ──POST /agent/stream (SSE)──▶  Python agent-service (FastAPI, async)
  input tray + canvas                                     LangGraph: Router→Planner→Drawer→Critic
  (applies streamed actions)                              tools: parse OpenAPI/SQL/code · RAG (pgvector)
        ▲                                                 Claude tool-calling · Langfuse · guardrails
        └──────────── streamed AgentAction[] ◀────────────┘  auth · quotas · MCP · BYOK
                                                          Supabase (Postgres + pgvector)
```

- **`agent/`** — Python FastAPI + LangGraph service (**where the engineering lives**). Runnable now.
- **`web/`** — tldraw canvas client (thin; forked from `tldraw/agent-template` in the Phase-0 spike).
- **`shared/`** — the client↔server contract (one schema → Zod + Pydantic).

## Quickstart (agent service)

```bash
cd agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add ANTHROPIC_API_KEY when wiring the LLM
uvicorn app.main:app --reload   # http://127.0.0.1:8000

# smoke test:
curl -N -X POST http://127.0.0.1:8000/agent/stream \
  -H 'content-type: application/json' \
  -d '{"message":"users table with orders","session_id":"dev"}'
```

You'll see `AgentAction` events stream back (the Phase-0 stub draws two boxes + an arrow).

## Roadmap

Phased plan (v0 deployed vertical slice → v1 depth → v2 stretch), eval design, backend pillar, and
resume framing all live in [`PLAN.md`](./PLAN.md).

## Tech stack

Python · FastAPI · LangGraph · Claude · pgvector · tldraw/React-TS · Supabase · Langfuse · Docker · GitHub Actions · MCP
