# 02 — Tech Stack

Python-first, boring-where-possible, owned-where-it-matters. Every choice below is judged on
three axes: **flexibility** (can we change direction cheaply), **maintainability** (one person
can hold it in their head), and **run cost** (target: whole product < $25/mo until revenue).

## Backend (the product's core)

| Layer | Choice | Why (and what we rejected) |
|---|---|---|
| Language | **Python 3.11+** | Team strength; best LLM ecosystem; async is mature. |
| Web framework | **FastAPI (async) + uvicorn** | Native SSE/streaming, Pydantic integration, tiny footprint. Rejected Django (heavy for an API-only service), Flask (weak async). |
| Agent orchestration | **Our own graph engine** (`app/graph/engine.py`, ~110 lines) | Full control, zero framework churn/lock-in, trivially debuggable. Rejected LangGraph (see ADR-002). |
| LLM SDK layer | **langchain-anthropic / langchain-openai** (thin client usage only) | Provider abstraction + structured-output/tool-calling for free. This is an SDK, not orchestration. If it ever fights us, we hand-roll tool-calling (flagged as a separate decision). |
| LLM providers | **OpenRouter** (default, cheap models) + **Anthropic direct** + **BYOK** | One abstraction (`app/llm.py`), env-switchable. Default model `openai/gpt-4o-mini` ($0.15/M in) — verified reliable for function-calling. Premium tier upgrades planner/critic to a Claude model. |
| Validation / contract | **Pydantic v2** | Shared-schema mirroring, structured LLM output, request validation — one tool for all three. |
| DB / ORM | **PostgreSQL + SQLAlchemy 2.0 async**; SQLite in dev | Postgres because pgvector (RAG) and every host has it managed. SQLAlchemy async keeps the whole service on one event loop. |
| Migrations | **Alembic** (from P3 onward) | The standard; nothing else worth considering. |
| Vector store | **pgvector** (inside the same Postgres) | RAG without a second database or vendor. Rejected Pinecone/Weaviate — cost and ops for zero benefit at our scale. |
| Auth | **Supabase Auth (JWT)**, verified in FastAPI middleware | Free tier covers thousands of users; we only verify tokens — no session infra to run. Rejected rolling our own auth (undifferentiated risk). |
| Rendering (vision critic) | **Pillow** | Rasterize planned actions → PNG server-side, no headless browser. Rejected Playwright screenshots (heavy, slow, flaky in containers). |
| Rate limiting / quotas | In-app (Postgres counters) first; Redis only if/when needed | Don't run Redis before something requires it. |

## Frontend (thin by policy)

| Layer | Choice | Why |
|---|---|---|
| Canvas | **tldraw SDK 5.x** (used directly, not forked) | Best-in-class canvas engine; we own only a small action-apply layer (`applyActions.ts`). Rejected forking tldraw's agent-template (bending its Cloudflare-Worker protocol to our contract was more risk than ~50 lines we own — ADR-001). Rejected Excalidraw (weaker programmatic API). |
| Framework / build | **React 19 + TypeScript + Vite** | tldraw is React; Vite is the no-config default. |
| Styling | **Hand-rolled CSS with design tokens** (light + dark) | Already built and polished; no Tailwind dependency for a one-surface app. |
| State | React state + tldraw store; **no state library** | The client is thin; adding Redux/Zustand would be ceremony. |
| Transport | **fetch + SSE parsing** (`transport.ts`) | No socket library until multiplayer (post-v1). |

## Infrastructure & DevEx

| Concern | Choice | Notes |
|---|---|---|
| Containerization | **Docker** (agent/Dockerfile, root docker-compose.yml) | Compose = one-command local prod-parity. |
| CI | **GitHub Actions** (ruff, mypy, pytest, tsc, build) | YAML parked at `.github/ci.yml.pending` until the token gets `workflow` scope. |
| Backend hosting | **Render free tier** at launch (UptimeRobot keep-alive on `/health`); Railway $5 / Render Starter $7 once real traffic arrives | See [07-deployment.md](./07-deployment.md) for trade-offs and upgrade triggers. |
| Frontend hosting | **Cloudflare Pages** (static Vite build) | $0, global CDN. |
| DB hosting | **Supabase** (Postgres + pgvector + Auth in one free tier) | One vendor covers three needs at $0 to start. |
| Observability | **Our own lightweight per-node tracing** (v1) + platform logs + UptimeRobot | Rejected Langfuse (ADR-003) — dropped with the framework; our tracing needs are per-node timings/tokens/cost, ~a table and a decorator. |
| Errors | **Sentry free tier** (both sides) | 5k events/mo free; wire in at P3. |

## Quality toolchain (already enforced)

| Tool | Scope |
|---|---|
| **ruff** (lint + format) | agent/ — config in `agent/pyproject.toml` |
| **mypy** (strict-leaning) | agent/ |
| **pytest** (+ pytest-asyncio) | agent/tests — 26 passing, offline-capable (`vision_enabled=False`) |
| **tsc --noEmit + oxlint** | web/ |

## Cost model (infra, monthly)

| Item | $/mo (launch) | $/mo (≈1k WAU) |
|---|---|---|
| Backend instance (Render free + keep-alive → paid later) | $0 | ~$7–15 (paid tier + replicas) |
| Postgres + Auth (Supabase) | $0 | $25 (Pro, when limits hit) |
| Frontend CDN (CF Pages) | $0 | $0 |
| Domain | ~$1 | ~$1 |
| LLM tokens (cheap tier default) | <$5 | ~$20–50 (usage-gated; BYOK offsets) |
| **Total** | **≈ $5** | **≈ $60–90** |

Compare: a single Eraser Pro seat is $15/mo. Our whole product at launch runs for less than one
competitor seat — that is the structural advantage the pricing strategy leans on.

## Version policy

- Python 3.11 floor (matches mypy cache/CI); 3.12 encouraged.
- Node 20 LTS floor for web builds.
- Pin direct dependencies (`requirements.txt` exact-ish, `package-lock.json` committed);
  upgrade deliberately, monthly, gates green.
