# PLAN-next — deploy se pehle sab complete

Rule: **ek phase = ek branch = ek PR**. Har phase ke end par gates green (pytest, ruff, mypy, web lint+build).
Paid LLM call sirf Phase 1 (Tier 2 recording, ~$0.05, user ne approve kiya). Baaki sab offline.

## Phase 0 — Safai (½ din)
- README, docs/04-roadmap "Where we are today", docs/02 + 07 (auth = apna, Supabase sirf Postgres) update.
- `.env.example` se Langfuse keys hatao.
- Web bundle code-split (`React.lazy` for Editor/tldraw), icons.tsx lint warning fix.
**Done when:** docs code se match karte hain, lint 0 warning.

## Phase 1 — Eval complete (1–2 din)
1. **Tier 2 record**: `pytest tests/eval/test_tier2.py --record` (gemini-3.7-flash, vision off, ~$0.05).
   Chalane se pehle `MAX_RUN_COST_USD` aur total cap confirm. Fixtures + `recorded_at`/`model` commit.
2. Replay mode mein tune: expectations fix, hard gates green.
3. **Thumbs up/down**: `runs.feedback` column (Alembic migration), `POST /runs/{id}/feedback`, UI buttons artifact row par.
4. **Judge** (`app/eval/judge.py`): 20 runs hand-label, judge agreement check. Agree na kare to ship nahi.
**Done when:** Tier 2 CI mein green, thumbs end-to-end kaam kare, agreement number repo mein.

## Phase 2 — Parity closers (3–4 din)
1. **Export**: PNG/SVG (tldraw export), Mermaid out (`emit_mermaid.py` from DiagramPlan).
2. **Mermaid in**: parse → plan → canvas (deterministic, no LLM).
3. **Share links**: signed read-only token, `/s/:token` read-only viewer, revoke.
4. Revert-to-turn (plans per message already stored).
5. Templates gallery (seed plans, zero-token).
**Done when:** export + share + mermaid round-trip tests green.

## Phase 3 — Agentic depth (4–5 din)
1. **Tracing**: span table + decorator per node, `/traces` viewer (RunRecord ke upar).
2. **RAG**: pgvector pattern library, planner retrieve → Tier 1/2 mein before/after measure.
3. **MCP server**: generate_diagram / edit_diagram tools.
4. `parse_code` tool (file → module/call graph).
5. BYOK encrypted at rest.
**Done when:** har item ka test + README mein ek measurable claim.

## Phase 4 — Parity polish (1–2 din)
Per-slot card width (2-up rows), note/annotation block, panel title icons.

## Phase 5 — Deploy (2–3 din)
1. Docker local-prod smoke (compose + Postgres).
2. Supabase Postgres, Render agent (single worker — throttle in-process), CF Pages web.
3. Prod env: ALLOWED_ORIGINS, COOKIE_SECURE=true, API subdomain of app, Resend, APP_URL.
4. Sentry + UptimeRobot `/health`.
5. Prod smoke: signup → verify → generate → share → export.
**Done when:** cold visitor ko live URL par diagram <30s mein mile, spend capped.

## Order logic
Eval pehle (baaki changes ko measure kar sakein) → features → depth → deploy. Deploy last kyunki tum chahte ho sab ek baar complete ho.
