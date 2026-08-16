# 08 — AI Features: Pipeline, Model Strategy, Cost, Evals

This doc specifies the AI feature set that must match or beat Eraser.io's, how each feature is
built, what each use costs us, and how quality is measured. Companion to
[01-architecture.md](./01-architecture.md) (the graph) and ADR-005/008/009.

## Feature inventory

### 1. Text → diagram (the DiagramGPT equivalent) — ✅ live
Freeform description → LLM planner (`planner_llm.py`) emits a **typed `DiagramPlan`**
(nodes, edges — soon groups/kinds/subtitles) via structured output / function-calling →
deterministic layout → streamed actions → critic loop.

Design points that beat one-shot generation:
- The LLM never emits coordinates or tldraw JSON — it emits *semantics*; deterministic layout
  guarantees geometric sanity. Hallucination surface is limited to the plan's content.
- The critic loop (below) fixes what the planner gets spatially wrong.
- P1 extends the plan vocabulary: `groups` (containers/swimlanes), node `kind`
  (service/store/decision/…), `subtitle`, `icon` — the planner's prompt and schema grow, the
  pipeline doesn't change (registry pattern, ADR-013).

### 2. Spec → diagram (our wedge; Eraser doesn't have it) — ✅ live
- **SQL DDL → ERD**: `parse_sql` → tables/columns/PK/FK → layout. Zero tokens, zero hallucination.
- **OpenAPI/Swagger → API surface**: `parse_openapi` (JSON/YAML) → tag-grouped operations → layout.
- v1: **code → module/call-graph** (`parse_code`), **Mermaid in** (P4).

Positioning rule (ADR-005): anything parseable is parsed. The marketing line is "unlimited
free schema diagrams — they cost us nothing, so we don't meter them."

### 3. Self-correcting critic — ✅ live (unique vs Eraser)
Two passes per iteration, bounded (`MAX_ITERATIONS=3`):
1. **Geometry** (`critique.py`, deterministic, free, authoritative): overlaps, crowding,
   dangling arrows → drives the refine loop (Drawer re-runs with `gap_scale ×1.5`).
2. **Vision** (`render.py` Pillow raster → `critic_vision.py`, one small multimodal call,
   best-effort): an LLM *looks at* the diagram and judges layout like a human would.

Each pass streams a `critique` SSE event — the UI's Critic strip makes self-correction a
*visible product moment*, not hidden machinery. P1 teaches the critic container-era failure
modes (group overflow, cross-group arrow tangles).

### 4. Conversational editing — 🔨 P4
Same endpoint, same graph. `canvas_context` carries focused-shape ids + viewport screenshot;
the planner receives the current plan and returns a **delta plan**; the Drawer diffs it into
`update/delete/create` actions. ("Split the payment service", "make this flow async".)

### 5. RAG pattern library — 🔨 v1
Curated, high-quality diagram patterns (auth flows, CQRS, event-driven, standard ERDs) stored
with embeddings in pgvector. Planner retrieves top-k patterns for the request and conditions
on them → structurally better plans from cheap models. The same curated set seeds the P4
templates gallery — one dataset, two features.

### 6. MCP server — 🔨 v1
Expose `generate_diagram` / `edit_diagram` as MCP tools so any MCP client (Claude, IDEs) can
drive Canvo. This replaces building per-app integrations and is itself a differentiator.

## Model strategy (ADR-009)

| Role | Default (free tier) | Pro tier | Notes |
|---|---|---|---|
| Planner (text → plan) | `openai/gpt-4o-mini` via OpenRouter | Claude Sonnet-class | Structured output must be *verified* per model before allowlisting |
| Vision critic | same cheap multimodal | same or better | Best-effort; skipped without a key |
| Router | heuristics (no LLM) | heuristics | LLM fallback only if heuristics misroute in practice |
| Edit planner (P4) | cheap | premium | Deltas are harder; expect premium to matter here |

Provider abstraction (`app/llm.py`) + `LLM_MODEL` env + BYOK keep every row swappable.
Empirical allowlist notes live next to the code: gpt-4o-mini reliable;
gemini-2.5-flash-lite hangs on function_calling; claude-3.5-haiku 404 on OpenRouter.
`build_chat_model`: timeout 45s, max_retries 2.

## Cost per generation (the number that funds the pricing strategy)

Rough tokens for a typical freeform generation (planner in+out, 1 vision pass):
~3–5k in / ~1–2k out on the cheap tier.

| Path | LLM calls | Est. cost |
|---|---|---|
| SQL / OpenAPI / Mermaid-in | 0 | **$0.000** |
| Text → diagram, no refine | 1 planner + 1 vision | ~**$0.002** |
| Text → diagram, worst case (3 iterations) | 1 planner + 3 vision | ~**$0.004–0.005** |
| Edit turn (P4) | 1 delta-planner + ≤1 vision | ~$0.002–0.003 |

⇒ 1,000 free AI generations ≈ **$2–5**. This is why the free tier can be generous while
Eraser meters "3 AI credits", and why Pro at $5–6 has healthy margin. Every new AI feature
PR must state its line for this table.

## Guardrails (v0 minimums → v1 full)

- **Bounded loops everywhere**: `MAX_ITERATIONS=3` (critic), `_MAX_STEPS=64` (engine) — no
  unbounded agent behavior, ever.
- **Caps** (P0): per-IP daily AI generations, payload size, per-run LLM-call ceiling.
- **Injection defense** (v1): user payloads (PRDs, specs) are *data*, fenced and labeled in
  prompts; planner output is schema-validated — a hostile PRD can at worst produce a weird
  diagram, never an action outside the contract.
- **Sanitization**: strip secrets-looking strings from payloads before they reach a
  third-party model; BYOK users bypass our keys entirely.
- **Degrade, don't die**: no key / provider down / `AI_DISABLED=1` → deterministic paths keep
  working; LLM paths return a typed, user-visible error event.

## Evaluation (how we prove "works as well as Eraser")

**Harness (v0 in P1, v1 later), lives in `agent/app/evals/`:**
1. **Golden set**: 10 → 50 inputs across kinds (text prompts incl. the JWT-auth reference,
   SQL schemas, OpenAPI specs), each with expectations.
2. **Deterministic checks** (free, in CI): geometry invariants (no overlaps, arrows bound,
   groups contain their members), plan-content checks (entities from the input appear;
   nothing invented on deterministic paths).
3. **LLM-as-judge** (manual/nightly, not per-commit): rubric scoring 1–5 on completeness,
   correctness, layout clarity, label quality — over the rendered PNG + plan.
4. **Before/after-critic table**: the same inputs scored with the critic disabled vs enabled —
   the headline number for the landing page ("self-correction improves layout score by X%").
5. **Model-gate**: any default-model change must run the full harness and not regress.

**Competitive benchmark (quarterly, manual):** same 5 prompts into Canvo and Eraser,
side-by-side screenshots, blind preference vote. This is the honest scoreboard for the
"works equally well" goal — and the marketing asset when we win.
