# 00 — Product Vision & Competitive Strategy

## One-liner

> Drop in what you already have — a PRD, an OpenAPI spec, a SQL schema, code, or a sentence —
> and get a live, editable, self-corrected diagram on an infinite canvas. Keep refining it
> conversationally.

## Why this product, why now

Eraser.io charges **$15/user/month** for its Pro plan, and its AI features (DiagramGPT) are
credit-gated even on paid tiers. Its core value — "describe a system, get a beautiful diagram" —
is now reproducible with commodity LLMs plus careful engineering. The expensive part of their
product is not the AI; it is the polish (layout quality, node cards, containers, dark theme) and
the workflow (doc + canvas side by side, sharing).

Our thesis:

1. **We can match output quality** with a hybrid pipeline: deterministic parsers + layered layout
   + an LLM planner + a self-correcting critic (geometry + vision). Most of that already runs.
2. **We can undercut on price structurally, not just tactically.** Deterministic paths (SQL → ERD,
   OpenAPI → API map) cost us $0 in tokens. LLM paths use cheap models (~$0.15/M input) behind a
   provider-abstraction layer, so a full diagram generation costs fractions of a cent. Eraser's
   credit anxiety ("1 of 3 AI credits") becomes our marketing wedge: **generous free tier**.
3. **We own the whole stack** — our own graph engine, our own layout, our own tracing. No
   per-seat framework costs, no vendor lock-in, tiny infra bill (see [07-deployment.md](./07-deployment.md)).

## Target users

| Segment | Job to be done | What wins them |
|---|---|---|
| Backend/platform engineers | Turn a schema or API spec into an accurate diagram for a design doc/PR | **Real-input grounding** — paste DDL, get a correct ERD, no hallucinated columns |
| Architects / tech leads | System design diagrams for RFCs and reviews | Layout quality: containers/swimlanes, node cards, decision diamonds |
| PMs / founders | "Explain this flow" diagrams from plain text | One prompt → clean diagram, editable afterwards, free tier |
| Students / interview preppers | System-design practice diagrams | Free tier + templates |

## Feature parity map vs Eraser.io

Legend: ✅ shipped in Canvo · 🔨 in progress / planned (roadmap phase in parentheses) · ➖ deliberately skipped for now

| Eraser.io feature | Canvo status | Notes |
|---|---|---|
| AI text → diagram (DiagramGPT) | ✅ | LLM planner with structured output; self-correcting critic on top (Eraser is one-shot) |
| Diagram-as-code (Eraser DSL) | 🔨 (P4) | We expose **Mermaid in/out** instead of a proprietary DSL — bigger ecosystem |
| Infinite canvas, shapes, arrows | ✅ | tldraw SDK — more polished editor core than Eraser's |
| Grouped/colored containers, swimlanes | 🔨 (P1 — Quality Pass) | Planner emits groups; layout gets layered top-down algorithm |
| Rich node cards (icon + title + subtitle), decision diamonds | 🔨 (P1 kinds/subtitles, P2 custom tldraw shapes) | Tier 2 = React card shape components, the exact Eraser look |
| Dark theme | ✅ | Design tokens, light + dark |
| Doc + canvas side-by-side ("Document / Both / Canvas") | 🔨 (P4) | Markdown pane with embedded live diagrams |
| **Spec ingestion: SQL → ERD, OpenAPI → API map** | ✅ | **Eraser does not have this** — our wedge feature |
| Self-correcting layout (vision critic) | ✅ | **Eraser does not have this** |
| Session persistence / files | ✅ | Snapshots via SQLAlchemy async; file manager UI planned (P3) |
| Auth, workspaces | ✅ auth / ➖ workspaces | Own email+password sessions (ADR-014); single-user by design for now |
| Sharing (read-only links) | 🔨 (P3) | Signed share links on snapshots |
| Real-time multiplayer | ➖ (post-v1) | tldraw sync exists; deferred — single-player + share links first |
| Export (PNG/SVG/Mermaid) | 🔨 (P4) | tldraw export APIs + Mermaid emitter |
| Templates gallery | 🔨 (P4) | Seeded from our pattern library (same data RAG uses) |
| Integrations (GitHub, Confluence…) | ➖ (post-v1) | MCP server planned instead — agent-native integration surface |

## Pricing strategy (draft — validate before launch)

| Tier | Price | Includes |
|---|---|---|
| Free | $0 | Unlimited deterministic generations (SQL/OpenAPI), N AI generations/day (cheap model), 10 files, share links |
| Pro | **$5–6/user/mo** (vs Eraser $15) | Unlimited AI generations (fair use), premium model for planner+critic, unlimited files, exports, doc mode |
| BYOK | $0–2/mo | Bring your own API key — we charge ~nothing; converts power users and derisks our token bill |

Rationale: our marginal cost per AI generation is <$0.005 on the cheap tier (see
[08-ai-features.md](./08-ai-features.md)), so a generous free tier is affordable and is the main
acquisition channel against Eraser's credit-gating.

## Differentiators (the moat, in one place)

1. **Real-input grounding** — schema/spec/code → diagram with zero hallucination on the
   deterministic paths. This is a *correctness* claim Eraser cannot make.
2. **Self-correcting agent** — geometry + vision critic loop, streamed live so users *see* the
   agent fix its own layout. Observable quality, not one-shot generation.
3. **Structural cost advantage** — own engine, cheap/tiered models, deterministic fast paths,
   BYOK. Lets us price at 1/3 of Eraser sustainably.
4. **Open ecosystem** — Mermaid in/out and an MCP server instead of a proprietary DSL and
   closed integrations.

## Non-goals (for v1)

- Real-time multiplayer editing (share links suffice; sync is a post-v1 project).
- Native apps; web only.
- A proprietary diagram DSL — Mermaid is the interchange format.
- Voice input (revisit after v1; it is an enhancement, not the core value).

## Success metrics

- **Activation:** % of new visitors who generate ≥1 diagram in first session (target >40% — no
  signup required for first generation).
- **Quality:** eval-harness diagram score (LLM-as-judge + geometry checks), before/after critic
  delta published on the landing page.
- **Cost:** infra + tokens per weekly-active user < $0.10.
- **Conversion:** free → Pro ≥ 3% once Pro exists.
