# Canvo — Conversational Agentic Diagramming Canvas

> An infinite canvas where you **talk or type** and a **LangGraph multi-agent system**
> (Planner → Drawer → Critic) powered by **Claude** draws, refines, and **self-corrects**
> diagrams live — with full tracing, evals, and an MCP interface.

**Status:** 🚧 Phase 0 (scaffold) — the agent service runs end-to-end with stub nodes; LLM
wiring, canvas client, and the infra layer land next. Full plan: [`PLAN.md`](./PLAN.md).

---

## Why this exists

A portfolio proof-of-work for **agentic-AI-engineer** roles. Every choice targets a hiring
signal: explicit multi-agent orchestration, typed tool-calling, observability, eval-driven
development, guardrails, and MCP. See [`PLAN.md` §3](./PLAN.md) for the feature ↔ requirement map.

## Architecture (hybrid)

```
tldraw client (React/TS)  ──POST /agent/stream (SSE)──▶  Python agent-service (FastAPI)
  canvas + action-apply                                    LangGraph: Planner → Drawer → Critic
  + visual context                                         Claude tool-calling · Langfuse · guardrails
        ▲                                                          │
        └──────────────── streamed AgentAction[] ◀────────────────┘
                                                          Supabase (sessions, snapshots, runs)
```

- **`web/`** — tldraw canvas client (forked from `tldraw/agent-template`; reuses action-apply +
  visual context). *Added in the Phase-0 spike.*
- **`agent/`** — Python FastAPI + LangGraph agent-service (the "brain"). Runnable now.
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
  -d '{"message":"draw a login flow","session_id":"dev"}'
```

You'll see `AgentAction` events stream back (two boxes + an arrow — the Phase-0 stub).

## Roadmap

Phase-by-phase plan, scope, eval design, and resume framing live in [`PLAN.md`](./PLAN.md).

## Tech stack

Python · FastAPI · LangGraph · Claude (Anthropic) · tldraw / React-TS · Langfuse · Supabase · Whisper · MCP
