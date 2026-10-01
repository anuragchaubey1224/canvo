# 04 — Roadmap

Phased from **today's working codebase** to a **paid product competing with Eraser.io**.
Each phase ends with something a real user can touch. Rule: **ship the deployed slice early,
then deepen** — a live URL is half the signal, and real-user feedback beats speculation.

## Where we are today (baseline — done ✅)

- **Own graph engine**: router → editor → specifier → planner → drawer → critic (refine loop).
- **SQL → ERD**, **OpenAPI → API surface** (deterministic), **freeform text → diagram** (Spec
  Writer + planner + validator), **conversational editing** (typed ops, `answer` intent).
- **Quality (P1/P2 done)**: groups, composition grid, A* router, custom shapes, geometry + vision critic.
- **Product shell**: landing, dashboard, chat rail, own auth (ADR-014), reset/verify email, Alembic.
- **Guardrails/measurement**: generation allowance, per-run cost cap, run ledger with tokens/cost/latency/outcome.
- **Eval**: Tier 1 golden set (24 cases) in CI; Tier 2 harness built, fixtures pending a recording run.
- ~220 tests, ruff/mypy/lint/build green, CI live, Docker + compose. **Not deployed yet.**
- Next: see `PLAN-next.md`.

---

## Phase 0 — Ship the public v0 (≈ 1 week) 🎯 *next up*

**Goal: a stranger can open a URL and generate a diagram.** Everything else builds on this.

- [x] CI live (`.github/workflows/ci.yml`).
- [ ] Deploy agent (Fly.io or Railway, one small instance) with managed Postgres (Supabase).
- [ ] Deploy web (Cloudflare Pages), point at the agent URL, lock down CORS.
- [ ] Server-side kill-switches: per-IP daily generation cap, payload size cap, model spend
      alarm (guardrails.py becomes real enough to protect the token bill).
- [ ] Minimal landing framing on the app page: what it does, 3 sample inputs, no signup wall.

**Exit criteria:** live URL; a cold visitor gets a diagram in <30s; token spend capped.

## Phase 1 — Quality Pass Tier 1: Eraser-level structure (≈ 1–2 weeks)

**Goal: output that visually competes with Eraser's** (reference: the JWT-workflow screenshot).
This is the highest-leverage work in the plan — output quality is the product.

- [ ] **Groups/containers** end-to-end: `DiagramPlan` gains groups → layout allocates container
      regions (colored, titled, numbered like Eraser's swimlanes) → drawer emits container +
      member shapes → new `create_group` action in the contract.
- [ ] **Layered top-down layout** replacing the 3-column grid: rank nodes by dependency depth
      (Sugiyama-lite), route arrows between layers, minimize crossings.
- [ ] **Node semantics**: `kind` (service, store, decision, start/end, external) + `subtitle` —
      decision → diamond, store → cylinder-ish geo, kind-based color tokens.
- [ ] Critic learns the new failure modes: container overflow, cross-group arrow mess.
- [ ] Eval set v0: 10 golden inputs (text + SQL + OpenAPI) with geometry assertions, run in CI.

**Exit criteria:** the JWT-auth prompt from the Eraser screenshot produces a grouped, layered,
colored diagram we're proud to screenshot side-by-side.

## Phase 2 — Quality Pass Tier 2: the Eraser look (≈ 1–2 weeks)

**Goal: rich node cards.** Built-in geo shapes can't match Eraser's card aesthetic.

- [ ] **ShapeRegistry** (ADR-013): open-set `kind` in the contract, client registry mapping
      kind → custom `ShapeUtil`, geo-box fallback for unknown kinds — this is what makes every
      future shape a local, cheap addition.
- [ ] Custom tldraw shape (React component): icon + title + subtitle card, theme-aware,
      selectable/resizable, serializes cleanly into snapshots.
- [ ] Icon set: curated open-source tech/logo icons (service, db, queue, client, cloud…),
      planner picks `icon` by node semantics.
- [ ] Container as custom shape (header band + count + accent color like Eraser's).
- [ ] Contract: `create_shape` carries `kind/icon/subtitle`; old clients ignore gracefully.

**Exit criteria:** side-by-side with Eraser on 5 prompts, blind viewers can't pick the $15 one.

## Phase 3 — Real users: auth, files, sharing, metering (≈ 2 weeks)

**Goal: people can come back, and we can afford them.**

- [x] Auth shipped — own sessions, not Supabase (ADR-014).
- [ ] File manager: sessions become named files owned by users; list/rename/delete UI.
- [ ] Share links: signed read-only tokens onto snapshots.
- [ ] Metering: `generations` table (input kind, model, tokens, cost, critic iterations) —
      this powers quotas *and* our cost dashboards *and* future billing.
- [ ] Quotas: free-tier daily AI-generation limit enforced server-side; deterministic paths
      unlimited (they cost us nothing — and that's a marketing line).
- [x] Alembic migrations.
- [ ] Sentry both sides; uptime monitoring.

**Exit criteria:** signup → create → save → share works; per-user cost visible in a query.

## Phase 4 — Parity closers: doc mode, Mermaid, exports, templates (≈ 2–3 weeks)

**Goal: close the remaining "but Eraser has…" gaps.**

- [ ] **Export**: PNG/SVG (tldraw export APIs) + **Mermaid out** (`emit_mermaid.py` from
      `DiagramPlan`) — diagram-as-code without a proprietary DSL.
- [ ] **Mermaid in**: paste Mermaid → parse → plan → canvas (cheap, deterministic).
- [ ] **Doc mode**: markdown pane beside the canvas (Document / Both / Canvas toggle),
      embedded live diagram references.
- [ ] **Templates gallery**: seeded from the curated pattern library.
- [ ] **Conversational edit**: `canvas_context` (focused shapes + screenshot) → delta plans →
      update/delete actions ("split the payment service", "make this async").

**Exit criteria:** the parity map in [00-product-vision.md](./00-product-vision.md) shows ✅ on
every "🔨 P4" row; edit-by-chat works on a diagram the agent didn't create.

## v1 — Depth: RAG, tracing, evals, BYOK, MCP (ongoing, interleaved)

The agentic/AI-engineering depth that is both product quality and portfolio signal:

- [ ] **RAG pattern library** (pgvector): curated good diagrams retrieved by the planner —
      measurably better structure on common asks (auth flows, CQRS, etc.).
- [ ] **Own per-node tracing**: span table + decorator; latency/tokens/cost per node; a tiny
      `/traces` viewer. (Replaces Langfuse — ADR-003.)
- [ ] **Eval harness v1**: golden set ×50, LLM-as-judge rubric, before/after-critic table
      published in the README/landing.
- [ ] **Guardrails v1**: prompt-injection defense on payloads, cost caps per run, sanitization.
- [ ] **BYOK**: user-supplied API keys (encrypted at rest) — near-zero-cost power tier.
- [ ] **MCP server**: expose diagram generation as MCP tools — agent-native integrations
      (Claude, IDEs) instead of building per-app plugins.
- [ ] **parse_code tool**: repo/file → module & call-graph diagrams.

## v2 — Monetize & grow (after real usage data)

- Billing (Stripe) on the Pro tier; pricing validated against usage from `generations`.
- Real-time multiplayer (tldraw sync) if share-link analytics demand it.
- Team workspaces; SSO if a customer asks (not before).
- Voice input (deferred enhancement).

## Standing risks & mitigations

| Risk | Mitigation |
|---|---|
| Token bill spikes from a free tier gone viral | Server-side caps from P0 day one; cheap model default; BYOK path; spend alarms |
| tldraw major-version churn | Thin client + our own apply layer = small blast radius; pin versions |
| Cheap-model function-calling flakiness | Verified model allowlist (gpt-4o-mini works; gemini-flash-lite hangs — documented); retries + timeout in `build_chat_model` |
| Eraser ships spec-ingestion | Our critic loop + open ecosystem (Mermaid/MCP) + price remain; speed is the real defense — ship P1/P2 fast |
| One-person bus factor | This docs set + ADRs + tests keep the codebase re-enterable |
