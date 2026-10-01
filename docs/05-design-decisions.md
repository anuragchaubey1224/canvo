# 05 — Design Decisions (ADRs)

Lightweight Architecture Decision Records. Status: **Accepted** unless noted. When a decision
is revisited, add a new ADR that supersedes the old one — never edit history.

Format: Context → Decision → Consequences (including what we gave up).

---

## ADR-001 — Hybrid architecture: thin tldraw client, deep Python service

**Context.** Canvas products usually put logic in the client. tldraw even ships an
`agent-template` (TypeScript, Cloudflare Workers) that would have given us an agent loop for
free — but on their protocol, in their runtime, in TypeScript.

**Decision.** Use the tldraw SDK directly in a thin Vite/React client; put *all* intelligence
in a separate async Python FastAPI service. Bridge them with our own ~50-line action-apply
layer and a single `AgentInput → streamed AgentAction[]` contract. We did **not** fork the
agent-template: bending its Worker protocol to our contract was more risk than owning the
small apply layer.

**Consequences.** (+) Agent is testable without a browser; client is replaceable; Python is
where the engineering depth lives. (+) Contract discipline forced from day one. (−) We
maintain the apply layer across tldraw upgrades (small, known surface). (−) Two deploys.

---

## ADR-002 — Own graph engine instead of LangGraph

**Context.** v1–v3 plans assumed LangGraph for Router→Planner→Drawer→Critic. Our actual needs:
a few nodes, one conditional loop, streaming of per-node updates.

**Decision.** Drop LangGraph. `app/graph/engine.py` (~110 lines) implements nodes, edges, one
conditional edge, sync+async execution, `astream` yielding `(node, update)` deltas, and a
`_MAX_STEPS=64` cap. Known trade-off accepted with eyes open: we lose the LangGraph resume
keyword, we gain full ownership, zero framework churn, and an engine we can explain line by
line — which is itself the stronger signal, and for the product means zero dependency risk.

**Consequences.** (+) No breaking-change treadmill; debugging is plain Python. (+) The engine
is a feature (observability hooks are ours). (−) Anything LangGraph gives free later
(checkpointing, human-in-the-loop) we build ourselves — acceptable; our graph is small.

---

## ADR-003 — Own lightweight tracing instead of Langfuse

**Context.** Observability was planned via Langfuse. After ADR-002, pulling in a third-party
observability stack for a handful of nodes contradicts the ownership direction and adds a
vendor + cost.

**Decision.** Build our own per-node tracing in v1: a span model (node, duration, tokens,
cost, iteration), a decorator on engine node execution, storage in Postgres, a minimal
`/traces` read endpoint. Platform logs + Sentry cover the rest.

**Consequences.** (+) Zero vendor cost/lock-in; tracing tailored to *diagram* metrics
(critic iterations, gap_scale changes). (−) No fancy UI — a table and a tiny viewer must do.

---

## ADR-004 — Keep langchain-* as the LLM SDK layer (for now)

**Context.** After dropping LangGraph, should the langchain client libraries go too?

**Decision.** Keep `langchain-anthropic`/`langchain-openai` strictly as the **SDK layer**:
provider abstraction + `with_structured_output(method="function_calling")`. This is not
orchestration. Dropping it means hand-rolling tool-calling across providers — a separate
decision to be flagged explicitly if these libraries ever fight us.

**Consequences.** (+) BYOK/provider-switching nearly free; structured output battle-tested.
(−) A heavyweight dependency used at ~5% of its surface; revisit if install size or breaking
changes bite.

---

## ADR-005 — Deterministic parsers before LLMs, always

**Context.** SQL and OpenAPI inputs have exact grammars. LLMs hallucinate columns and
endpoints; parsers don't. Tokens cost money; parsing is free.

**Decision.** Structured inputs are handled by deterministic tools (`parse_sql`,
`parse_openapi`, later `parse_code`, Mermaid-in). The LLM planner is reserved for freeform
text and (later) edit deltas. The Router chooses; an LLM never sees content a parser can handle.

**Consequences.** (+) Correctness guarantee Eraser can't make; zero marginal cost on our
wedge features; unlimited free-tier deterministic generations become a marketing weapon.
(−) Every new structured input type needs parser + layout + tests (bounded, well-trodden work).

---

## ADR-006 — SSE (one-way stream) now; WebSockets only with multiplayer

**Context.** The agent streams actions to the client; the client sends one request per turn.

**Decision.** Server-Sent Events over a plain POST. No socket infra until real-time
multiplayer (post-v1) genuinely requires it.

**Consequences.** (+) Plain HTTP: trivial to curl, proxy, retry, load-balance; no sticky
sessions. (−) No server→client push outside a request — fine for the current model.

---

## ADR-007 — Postgres for everything (relational + vectors), SQLite in dev

**Context.** We need relational data (sessions, users, metering), vector search (RAG), and
low ops burden.

**Decision.** One Postgres (Supabase-managed) with pgvector. SQLite locally for zero-setup
dev. Repository layer (`app/db/repo.py`) keeps ORM out of routes. Alembic from P3.

**Consequences.** (+) One database to run, back up, and pay for ($0 to start). (−) SQLite/PG
behavior drift — mitigated by CI eventually running tests against Postgres.

---

## ADR-008 — Critic loop: cheap-deterministic first, vision best-effort, always bounded

**Context.** Self-correction is a differentiator, but LLM-vision on every iteration is slow
and costs money, and unbounded loops are a reliability and cost hazard.

**Decision.** Two-pass critic: deterministic geometry (`critique.py`, free, authoritative —
drives the loop) then vision (`render.py` Pillow raster → one small multimodal call,
best-effort, degrades to skip without a key). Loop bounded by `MAX_ITERATIONS=3`; each retry
widens `gap_scale` ×1.5. Every pass streams a `critique` event — self-correction is a visible
product feature, not hidden machinery.

**Consequences.** (+) Predictable worst-case latency/cost; works fully offline in tests.
(−) Vision judgments that need non-spacing fixes are logged, not yet acted on (future work).

---

## ADR-009 — Cheap-model default with a verified allowlist; premium models are a paid tier

**Context.** Cost is a product feature (we undercut a $15 competitor). Cheap models vary
wildly in function-calling reliability — empirically: `openai/gpt-4o-mini` works;
`google/gemini-2.5-flash-lite` *hung* on structured output; `anthropic/claude-3.5-haiku` 404s
on OpenRouter.

**Decision.** Default model via OpenRouter (`LLM_MODEL` env), currently `openai/gpt-4o-mini`
($0.15/M input). Maintain an allowlist of *verified* models; never switch defaults without
running the eval set. `build_chat_model` enforces timeout=45s, max_retries=2. Premium models
(Claude Sonnet-class) become the Pro-tier planner/critic. BYOK bypasses our bill entirely.

**Consequences.** (+) Marginal cost per generation < $0.005; free tier is affordable.
(−) Cheap-model plan quality ceiling — mitigated by the critic loop and RAG patterns.

---

## ADR-010 — Mermaid as the interchange format; no proprietary DSL

**Context.** Eraser has its own diagram DSL. Building one is a moat for them and a trap for
us (adoption cost, lock-in perception, spec maintenance).

**Decision.** Mermaid in and Mermaid out (P4). Internally the typed `DiagramPlan` stays our
richer representation; Mermaid is the import/export boundary.

**Consequences.** (+) Instant compatibility with GitHub/Notion/docs ecosystems; import path
from every "mermaid generator" tutorial out there. (−) Mermaid can't express everything our
plan can (icons, containers styling) — exports are lossy-but-useful; PNG/SVG cover fidelity.

---

## ADR-011 — Supabase for auth + DB hosting; we only verify JWTs *(superseded by ADR-014 for auth; Supabase still hosts Postgres)*

**Context.** Auth is undifferentiated heavy lifting with security downside; we need it by P3.

**Decision.** Supabase Auth issues JWTs; FastAPI middleware verifies signatures locally
(no per-request auth-server round-trip). Anonymous usage remains for first-touch (no signup
wall before the first diagram). Same vendor hosts Postgres+pgvector — one free tier, three needs.

**Consequences.** (+) $0 to start, minutes to integrate, standard JWT semantics. (−) Vendor
coupling for identity — bounded: standard JWT + Postgres export mean migration stays feasible.

---

## ADR-014 — Own sessions-based auth instead of Supabase Auth / JWT

**Context.** ADR-011 planned Supabase Auth. By P3 we needed data isolation, a per-account
generation allowance and recovery flows tied tightly to our own schema.

**Decision.** Email+password in `app/auth/`: Argon2id (OWASP floor, transparent rehash,
dummy verify on missing accounts), opaque `token_urlsafe(32)` session tokens (only SHA-256
stored) in an httpOnly+SameSite=Lax+Secure cookie, sliding 30-day / 90-day-absolute expiry.
Reset/verify links are single-use, purpose-bound, short-lived and stored hashed. Every repo
accessor takes `user_id`.

**Consequences.** (+) Instant revocation, no JWT pitfalls, one fewer vendor on the identity
path. (−) We own the security surface (covered by `test_auth.py`, `test_recovery.py`); login
throttle is in-process, so prod runs one worker until Redis; API must be a subdomain of the
app (Lax cookie). Supabase remains the Postgres host only.

---

## ADR-012 — The contract evolves additively; one commit touches all three mirrors

**Context.** `shared/actions.schema.json` ⇄ `schema.py` ⇄ `types.ts` can silently drift.

**Decision.** Additive-only within a major version (optional fields, new action types clients
may ignore). Breaking changes bump a stream-preamble `version`. Any contract change updates
all three files in the same commit with server tests + client type-check. (Future hardening:
generate both sides from the JSON schema.)

**Consequences.** (+) Old clients keep working mid-deploy; the contract stays reviewable in
one diff. (−) Discipline-based until codegen exists.

---

## ADR-013 — Extensible shape system: a shape registry, not hardcoded shape types

**Context.** The Eraser look (P2) needs custom tldraw shapes (node cards, containers,
diamonds), and we want **full flexibility to add any custom shape later** — new node kinds,
new visual styles, even user-defined shapes — without touching the agent graph or breaking
the contract each time.

**Decision.** Shapes are data-driven through a **registry pattern on both sides**:

- **Contract:** `create_shape` carries a semantic `kind` (string, open set — e.g. `service`,
  `datastore`, `decision`, `queue`, `client`, `note`…) plus a generic props bag
  (`title`, `subtitle`, `icon`, `color`, size hints). The schema does **not** enumerate a
  closed list of kinds — new kinds are additive data, not schema changes.
- **Client:** a `ShapeRegistry` (`web/src/shapes/`) maps `kind` → renderer. Registered kinds
  render as custom tldraw `ShapeUtil`s (React card components, containers, diamonds);
  **unknown kinds always fall back** to a sensible default (labeled geo box) so old clients
  and new kinds never break each other (composes with ADR-012).
- **Server:** layout treats shapes through a small `ShapeSpec` (footprint, ports/anchor rules)
  looked up by `kind`, with a default spec — adding a shape = one registry entry + optional
  spec, zero engine/graph changes.
- **Users keep the full tldraw toolset** (freehand draw, geo shapes, text, arrows) alongside
  agent-drawn shapes; agent shapes are ordinary editor shapes — selectable, editable,
  serialized in snapshots like everything else.

**Consequences.** (+) Adding a new shape is a bounded, local change (client renderer +
optional layout spec + planner vocabulary), enabling fast visual iteration toward and beyond
the Eraser look. (+) Fallback keeps forward/backward compatibility automatic. (−) Custom
`ShapeUtil`s must handle serialization, hit-testing, and theming carefully — each new shape
carries real UI work; the registry makes it *local*, not *free*.
