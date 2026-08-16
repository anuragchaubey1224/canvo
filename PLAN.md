# Canvo — Spec-to-Diagram Agentic Canvas (Solidified Plan v3)

> One-liner: *"Turn your specs, docs, and ideas into live, editable diagrams. A multi-tool
> LangGraph agent (Router → Planner → Drawer → Critic) reasons over real inputs — a PRD, an API
> spec, a SQL schema, code, or a plain description — draws on an infinite canvas, and self-corrects."*

**North star (3 non-negotiable conditions, set by the user):**
1. **Proper Python agentic AI** — genuine multi-tool agent, retrieval, memory, self-correction; not a toy.
2. **Clear advantage for AI-Engineer + Agentic-AI + Python-backend roles** — depth on all three.
3. **A real product people actually use** — deployed, usable, polished; not a demo script.

Every decision below is judged against these three. **Rule: `web/` (tldraw) stays thin — the
engineering lives in `agent/` (Python). That's what makes Python the star.**

---

## 0. v2 → v3 refactor (what changed after the "make it job-perfect" review)

| # | v2 | v3 (this) | Why (which condition) |
|---|---|---|---|
| 1 | Agent only draws shapes (narrow tool surface) | **Multi-tool agent that ingests real inputs** (PRD / OpenAPI / SQL / code / text) via parser + **RAG** tools | Cond. 1 — "draw shapes" is too thin for *agentic depth*; real inputs + retrieval = genuine agent |
| 2 | Voice-first, headline MVP | **Voice → v1 enhancement** | Cond. 2 — voice isn't the core signal for these roles; it steals time from depth |
| 3 | Production-backend concerns scattered | **"Production backend & DevEx" = first-class pillar** (auth, Postgres+migrations, rate-limit, tests, CI, Docker, deploy) | Cond. 2 — this is the *Python-backend* advantage |
| 4 | RAG/memory = stretch | **Retrieval of diagram patterns (pgvector) = core** | Cond. 1 — RAG is a top agentic-AI signal |
| 5 | Scope = "build it all" | **Vertical-slice `v0` deployed early, then deepen** | Cond. 3 — a usable public product beats a perfect unshipped one |
| 6 | Name "Sketchpilot" | **Canvo** (matches repo `anuragchaubey1224/canvo`) | consistency |

**Kept:** hybrid architecture (tldraw client + Python/LangGraph brain), Planner→Drawer→Critic,
Langfuse observability, eval-driven dev, guardrails, MCP, BYOK/provider-abstraction.

---

## 1. Product vision & positioning

- **What it is:** you drop in *real material* — a PRD, an OpenAPI spec, a SQL schema, a code snippet,
  or just a sentence — and a multi-tool agent turns it into a **live, editable diagram** on an infinite
  canvas. You keep refining conversationally ("split the payment service", "make this async"); the agent
  re-reads the canvas each turn and self-corrects layout/overlaps.
- **Why it's more than "text → diagram":** the agent *reasons over structured inputs* (parses a schema
  into tables+relations, an OpenAPI doc into flows), *retrieves* proven diagram patterns (RAG), and
  *critiques its own output* with vision. That's a real agent, not a prompt template.
- **Who it's for:** engineers/architects/PMs who want an accurate first-draft diagram from something they
  already have (a spec, a schema, a repo), editable live — instead of dragging boxes for an hour.

**Differentiators (the moat):**
1. **Real-input grounding** — spec/schema/code → diagram, not just freeform text.
2. **Multi-tool observable agent graph** — Router → Planner → Drawer → Critic, with RAG + vision self-correction, fully traced.
3. **Eval-driven & production-grade** — measured accuracy (before/after critic), deployed, auth'd, tested.

---

## 2. Prior-art & competitive landscape

| Project | Does | Doesn't (our gap = edge) |
|---|---|---|
| `Agents365-ai/tldraw-skill` (117★) | NL → `.tldr`, 6 presets, vision self-check | text-only skill; **no real-input parsing, no RAG, no hosted app, no infra** |
| tldraw `agent-template` | canvas + single-agent framework (TS/CF) | **no multi-tool graph, no Python/LangGraph, no evals/tracing/RAG** |
| Excalidraw / Eraser AI | text → diagram, polished | one-shot; **no spec-ingestion, no self-correcting critic, closed** |

> **Takeaway:** the *spec/doc/code → diagram* angle + observable multi-tool agent + evals is unoccupied.
> Don't duplicate `tldraw-skill` (presets/vision it has); go past it (real inputs + RAG + product + infra).

---

## 3. Job-signal map — feature ↔ 2026 requirement (all three role buckets)

| Requirement | In Canvo | Role bucket |
|---|---|---|
| Multi-agent orchestration | LangGraph Router→Planner→Drawer→Critic (§5) | Agentic |
| Tool use / API orchestration | parser tools (OpenAPI/SQL/code) + canvas actions (§5) | Agentic / AI-Eng |
| **RAG / retrieval / vector DB** | retrieve diagram patterns via pgvector (§6b) | AI-Eng / Agentic |
| Structured outputs / tool-calling | Pydantic schemas → Claude tool-use (§4) | AI-Eng |
| Multimodal / vision grounding | screenshot + shapes → Critic (§5) | AI-Eng |
| Observability / tracing | Langfuse per-node (§6a) | Agentic / AI-Eng |
| Evaluation / LLM-as-judge | eval harness, before/after critic (§6c, §13) | AI-Eng |
| Guardrails / autonomy control / injection defense | safety layer (§6d) | Agentic |
| Memory / state | session + conversation + semantic (§6e) | Agentic |
| MCP | agent as MCP server (§6f) | Agentic |
| **Async API design + streaming** | FastAPI async, SSE→WS (§7) | **Python backend** |
| **Auth + rate-limit + quotas** | Supabase Auth/JWT, per-user quota (§7) | **Python backend** |
| **DB + migrations** | Postgres + pgvector + Alembic (§7, §8) | **Python backend** |
| **Testing + CI/CD + Docker + deploy** | pytest, ruff/mypy, GH Actions, Docker, Fly/Railway (§7) | **Python backend** |
| Cost/latency optimization | prompt caching, model-tiering, streaming (§9) | AI-Eng |
| Provider abstraction / BYOK | Anthropic/OpenRouter/OpenAI-compatible (§6g) | AI-Eng / backend |

> Genuinely ship ~12+ of these *with numbers + a live URL* → a standout piece for all three buckets.

---

## 4. Architecture (v3 — hybrid, widened inputs)

```
┌──────────────────────────────────────────────────────────────────┐
│  web/  — tldraw client (React/TS)   [thin; template reuse]         │
│   input tray (paste PRD / OpenAPI / SQL / code / text; file drop)  │
│   chat panel · tldraw canvas (applies streamed actions live)       │
└───────────────┬───────────────────────────────▲──────────────────┘
    AgentInput = {message, input_kind?, payload,  │ AgentAction[] (SSE→WS)
      canvas_context:{focused,blurry,screenshot}} │
                ▼                                  │
┌──────────────────────────────────────────────────────────────────┐
│  agent/  — Python FastAPI service  (async)   [the engineering]     │
│                                                                    │
│  LangGraph:  ROUTER ─▶ PLANNER ─▶ DRAWER ─▶ CRITIC ─┐              │
│                 │         ▲                          │ refine loop  │
│   tools:        │         └────────── (issues,iter<N)┘  (bounded)  │
│    parse_openapi / parse_sql / parse_code / retrieve_patterns(RAG) │
│    + canvas actions (create/update/delete/connect)                 │
│                                                                    │
│  Claude tool-calling · prompt caching · model-tiering              │
│  Langfuse tracing · guardrails · Auth/JWT · rate-limit · quotas    │
│  MCP server (same graph as a tool) ──────────────────────────────▶ │  Claude Desktop / Cursor
└───────────────┬───────────────────────────────────────────────────┘
                ▼
   Supabase Postgres (+ pgvector): users, sessions, snapshots,
                                   chat_turns, runs, pattern_embeddings
```

**Client↔server contract (get right early):** `AgentInput` → streamed `AgentAction[]`. One schema
spec (`shared/actions.schema.json`) → Zod (client) + Pydantic (server), contract-tested. Transport:
**SSE (v0) → WebSocket (v1)**.

---

## 5. The agent graph (multi-tool, the depth)

LangGraph `StateGraph`. State carries the run (input, parsed structure, plan, actions, critique,
iterations, cost).

**Nodes:**
1. **Router** — classify input (`text | prd | openapi | sql | code`) + pick diagram type + which parser tool.
2. **Planner** — parsed structured data **+ retrieved patterns (RAG)** → `Plan` (nodes/edges/layout hint). Cheap model (Haiku 4.5).
3. **Drawer** — `Plan → AgentAction[]` via typed tool-calling; streams to canvas. Sonnet 5.
4. **Critic** — screenshot + shapes → `Critique` (overlaps? missing? intent-match?). Vision. Sonnet 5 (Opus 5 for hard cases).

**Tools available to the graph:**
- `parse_openapi(spec) → endpoints/flows`
- `parse_sql_schema(ddl) → tables/relations` (→ ERD)
- `parse_code(snippet) → modules/deps` (start with pasted code; repo-crawl = stretch)
- `retrieve_patterns(query) → few-shot diagram exemplars` (pgvector RAG grounding)
- canvas actions: `create / update / delete / connect shape`

**Loop guard:** Critic → conditional edge → `refine` (back to Drawer, or Planner for structural misses)
if `has_issues and iterations < N(=3) and cost < CAP`, else `END`. Every node = one Langfuse span.

**Model IDs (2026):** `claude-haiku-4-5` (router/planner), `claude-sonnet-5` (drawer/critic),
`claude-opus-5` (hard critique, optional). Prompt caching on static system/schema parts.

---

## 6. Agentic-infra layer (the senior signal)

### 6a. Observability — **Langfuse** (self-host, free) [+ LangSmith optional]
Per-node span: prompt, model, tokens, cost, latency, output. Full run trace incl. iterations. README
mein trace screenshot = instant credibility.

### 6b. Retrieval / RAG — **pgvector**
Vector store of diagram patterns / exemplars (and, later, the user's own past diagrams). Planner
retrieves relevant patterns to ground layout + few-shot. Embeddings via a small model. This is a
core AI-Eng signal, not a stretch.

### 6c. Evaluation harness (core deliverable) — see §13
20 fixed prompts, LLM-as-judge (calibrated), structural metrics, **before/after-critic** accuracy table.

### 6d. Guardrails / safety
Cost cap per run · iteration cap (N≤3) · **prompt-injection defense** (user/spec content can't override
system or tool perms; red-team set) · schema-validate + sanitize actions before applying.

### 6e. Memory / state
Session memory (canvas snapshot, Supabase) · conversation memory (last-N turns) · **semantic memory**
(past diagrams embedded → retrievable; ties into §6b).

### 6f. MCP server
Expose the graph as an MCP tool (`draw_diagram`) via FastMCP/Python SDK → usable from Claude Desktop/Cursor.

### 6g. Provider abstraction + BYOK
`agent/app/llm.py`: Anthropic / OpenRouter / any OpenAI-compatible. Per-request BYOK (`AgentInput.llm`);
user keys used per-request, **never logged/persisted**, HTTPS only.

---

## 7. Production backend & DevEx (first-class pillar — the Python-backend advantage)

This is what a backend interviewer probes. Treat it as core, not polish.

- **API:** FastAPI, fully **async**; `pydantic-settings` config; **structured logging** (structlog);
  consistent error model; OpenAPI docs. Streaming: **SSE (v0) → WebSocket (v1)**.
- **Auth:** Supabase Auth (verify JWT) — or signed API keys for the earliest slice.
- **Data:** Supabase **Postgres + pgvector**; **Alembic migrations**; a thin repository layer (no ORM-in-routes).
- **Limits:** per-user **rate-limiting + quotas** (crucial with LLM cost + BYOK).
- **Testing:** **pytest** — unit (parsers, guardrails, graph nodes with mocked LLM), integration
  (API + DB), contract test (Zod↔Pydantic). Coverage tracked. Eval suite runnable in CI (smoke subset).
- **Quality:** **ruff** + **mypy** + pre-commit.
- **CI/CD:** **GitHub Actions** (lint → typecheck → test). **Docker** + `docker-compose` (agent + postgres).
  **Deploy** agent to Fly.io/Railway/Render; DB on Supabase; web on Vercel/Netlify.
- **Observability in prod:** Langfuse + structured logs (+ OpenTelemetry later).

---

## 8. Data model (Supabase / Postgres + pgvector)

- `users` — (Supabase Auth) id, email, plan/quota
- `sessions` — id, user_id, title, created_at
- `snapshots` — session_id, tldraw store JSON, updated_at (debounced autosave)
- `chat_turns` — session_id, role (user/router/planner/drawer/critic), content, tokens, cost, latency, ts
- `runs` — session_id, langfuse_trace_id, input_kind, iterations, total_cost, verdict (analytics/eval)
- `pattern_embeddings` — id, kind, label, embedding (vector), payload (RAG store)

---

## 9. Tech stack (final v3)

| Layer | Choice | Why |
|---|---|---|
| Canvas / frontend | **tldraw** (agent-template client, thin fork) React+TS+Vite | reuse canvas + action-apply + visual context |
| **Agent service** | **Python · FastAPI (async) · LangGraph** | job-target stack; observable multi-tool orchestration |
| LLM | **Claude** — Sonnet 5 (drawer/critic), Haiku 4.5 (router/planner), Opus 5 (hard critique) | best tool-calling + vision; model-tiering |
| Provider layer | Anthropic · **OpenRouter** · OpenAI-compatible (+ **BYOK**) | flexibility; users bring own key/quota |
| Schemas | **Pydantic** ↔ **Zod**, one shared spec, contract-tested | typed, validated, drift-guarded |
| Retrieval | **pgvector** + embeddings | RAG grounding of diagram patterns |
| Observability | **Langfuse** (self-host) [+ LangSmith] | per-node tracing |
| Evals | LangGraph runner + LLM-as-judge | before/after numbers |
| Persistence | **Supabase (Postgres + pgvector)** + **Alembic** | data + migrations |
| Backend quality | pytest · ruff · mypy · pre-commit | Python-backend signal |
| CI/CD | **GitHub Actions** · **Docker** · Fly.io/Railway | shippable + reproducible |
| Transport | SSE (v0) → WebSocket (v1) | simple first, bidirectional later |
| MCP | FastMCP / Python MCP SDK | agent-as-tool |
| Voice (v1) | Web Speech → Whisper (Python) → TTS | multimodal bonus, later |

---

## 10. Repo structure (monorepo)

```
canvo/
├── web/                 # tldraw client (thin; forked in Phase-0 spike)
├── agent/               # Python FastAPI + LangGraph service  ← the engineering
│   ├── app/
│   │   ├── main.py           # FastAPI: /health, /agent/stream (SSE)
│   │   ├── schema.py         # Pydantic contract + BYOK
│   │   ├── llm.py            # provider abstraction (Anthropic/OpenRouter/…)
│   │   ├── guardrails.py     # caps, injection defense, sanitize
│   │   ├── graph/            # router, planner, drawer, critic + build
│   │   ├── tools/            # parse_openapi, parse_sql, parse_code, retrieve_patterns
│   │   ├── rag/              # embeddings + pgvector store
│   │   ├── db/               # models, repositories, Alembic migrations
│   │   ├── auth/             # JWT verify, quotas, rate-limit
│   │   ├── obs/              # Langfuse setup, structured logging
│   │   ├── mcp/              # MCP server
│   │   └── evals/            # dataset + judge + runner + report
│   ├── tests/                # unit + integration + contract
│   ├── Dockerfile · docker-compose.yml · pyproject.toml
├── shared/              # one schema spec → Zod + Pydantic mirror + contract test
├── .github/workflows/   # CI: lint → typecheck → test
└── README.md            # architecture, trace + eval screenshots, demo GIF, live URL
```

---

## 11. Scope (phased around a shippable v0)

### Phase 0 — Spike (de-risk integration first) — *partly done*
- [x] Monorepo scaffold; runnable FastAPI + LangGraph stub; contract file; git repo pushed.
- [ ] Fork tldraw `agent-template` into `web/`, run **as-is**, learn the client↔server contract.

### v0 — Usable & DEPLOYED vertical slice ("done" = a stranger can use it at a URL)
- [ ] One real input path end-to-end: **text/description OR SQL schema → Planner→Drawer → live canvas** (Python SSE).
- [ ] `parse_sql_schema` tool (first real "tool"); Router picks it.
- [ ] Session persist (Supabase); reload restores canvas.
- [ ] Langfuse tracing on every node.
- [ ] Dockerized; **deployed** (agent + web + DB); basic pytest + GitHub Actions CI green.

### v1 — Depth & polish (the resume sell)
- [ ] **Critic node + vision refine loop** (bounded).
- [ ] More inputs: **OpenAPI → flows**, **pasted code → modules**.
- [ ] **RAG**: `retrieve_patterns` over pgvector; grounds Planner.
- [ ] **Auth + quotas + rate-limit**; guardrails (caps, injection, sanitize).
- [ ] **Eval harness** + before/after-critic accuracy table.
- [ ] **MCP server**; presets; export (PNG/SVG) + share link.
- [ ] Test coverage solid; mypy/ruff clean; README with traces + numbers + demo.
- [ ] **Voice** (Web Speech → Whisper); WebSocket transport.

### v2 — Stretch (bonus)
- [ ] Repo-crawl → architecture diagram · multiplayer (tldraw sync) · TTS + barge-in · A2A second agent.

---

## 12. Roadmap (solo, part-time)

| Week | Goal |
|---|---|
| 1 | Phase-0 spike (tldraw template as-is, learn contract) + backend skeleton hardening (settings, logging, structure, DB conn). |
| 2 | **Vertical slice:** text/SQL → Planner→Drawer → canvas via Python SSE; Supabase persist; Langfuse. |
| 3 | Dockerize + CI + **deploy**. **v0 live & usable at a URL.** |
| 4 | Critic + refine loop; add OpenAPI/code inputs; `retrieve_patterns` (pgvector RAG). |
| 5 | Auth + quotas + rate-limit; **eval harness** + before/after table; tests to solid coverage. |
| 6 | MCP server; presets; export/share; README (traces + numbers + demo). **v1 done / portfolio-ready.** |
| 7+ | Voice, repo→diagram, multiplayer. |

> Full-time → compress to ~3.5–4 weeks. **Guard:** don't skip the v0 deploy (W3) to chase depth —
> a live URL is half the hiring signal. Integration (W1–2) is the real technical risk; don't rush it.

---

## 13. Eval harness (build properly)

- **Dataset:** 20 prompts across input kinds (description, SQL DDL, OpenAPI) → `agent/app/evals/dataset.jsonl`.
- **Metrics:** (a) structural (shapes/edges vs expected), (b) **LLM-as-judge** intent-match 0–1 (hand-calibrate on ~5),
  (c) Critic caught/fixed a real error, (d) iterations to converge, (e) latency, (f) cost.
- **Headline:** WITHOUT vs WITH critic loop → accuracy **X% → Y%**. Use in README + resume + interview.
- **CI:** a small smoke subset runs in GitHub Actions.

---

## 14. Resume framing + interview prep

**Resume bullet:**
> **Canvo — Spec-to-Diagram Agentic Canvas**
> Built a **multi-tool LangGraph agent** (Router→Planner→Drawer→Critic) that turns specs (OpenAPI, SQL
> schemas, code, or plain text) into live, editable diagrams and **self-corrects** with **vision**.
> Python/FastAPI (async) backend: **RAG** over pgvector, typed **tool-calling** (Pydantic), **prompt-injection
> guardrails**, **BYOK** provider abstraction, **JWT auth + per-user quotas**, and an **MCP** interface.
> Instrumented every node with **Langfuse** and built an **eval harness** (LLM-as-judge) showing the
> critic loop lifted diagram accuracy **X%→Y%**. Dockerized, CI-tested, deployed.
> Stack: Python, FastAPI, LangGraph, Claude, pgvector, tldraw/React-TS, Supabase, Langfuse, Docker, GH Actions.

Covers: multi-agent ✓, tool-use ✓, RAG ✓, evals ✓, observability ✓, guardrails ✓, MCP ✓, async backend ✓,
auth/limits ✓, tests/CI/Docker/deploy ✓, multimodal (v1) ✓.

**They'll grill you on:** how you measure/debug agents (Langfuse + evals) · loop termination (caps + edge) ·
injection defense (separation + red-team) · judge trust (calibration) · model-tiering (cost) · RAG design
(what/why embedded) · async + backpressure in streaming · how it differs from `tldraw-skill`.

---

## 15. Risks & guardrails

- **Integration (biggest)** — tldraw client ↔ custom Python backend. *Mitigate:* Phase-0 spike, one action path first.
- **Scope creep (v3-critical)** — "perfect product" temptation. *Mitigate:* ship v0 deployed at W3; depth after.
- **Frontend eats Python time** — *Mitigate:* keep `web/` thin, reuse template, invest in `agent/`.
- **Schema drift** (Zod/Pydantic) — one spec + contract test in CI.
- **LLM cost/latency** — critic N≤3, Haiku router/planner, prompt caching, stream, quotas.
- **"Just another AI diagram tool"** — loud README: real-input grounding + observable graph + eval numbers + live URL.
- **Don't reinvent canvas/collab** (tldraw) · **don't duplicate `tldraw-skill`** (go past it).

---

## 16. Immediate next steps

1. **Phase-0 spike:** fork tldraw `agent-template` into `web/` (`npm create tldraw@latest` → agent kit),
   run as-is with an Anthropic key, draw one diagram, and note exactly what the client sends/applies.
2. Point the client transport at our Python `/agent/stream` (SSE) for a single "create shapes" path.
3. Replace the graph stubs with real nodes: start with **Router + Planner + Drawer** and the first tool
   (`parse_sql_schema`) → SQL DDL → ERD on canvas. (Critic + RAG come in v1.)
4. Stand up Supabase (Postgres) + persist a session; wire Langfuse.
5. Dockerize + CI + deploy → **v0 live**. Then follow §12.

---

*Plan v3 solidified 2026-08-16. Direction: Python-heavy agentic-AI + backend roles; a real, deployed,
multi-tool spec-to-diagram agent. Verified against: tldraw agent-template, prior-art `tldraw-skill`,
2026 agentic-AI/AI-Eng/Python-backend job requirements.*
