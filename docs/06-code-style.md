# 06 — Code Style & Quality Gates

The style is already embodied in the codebase; this doc makes it explicit so the codebase
stays coherent as it grows. When in doubt: **match the file you're editing.**

## Universal rules

1. **Small, typed, boring.** Prefer plain functions over classes, explicit over clever,
   ~fewer than 300 lines per module before considering a split.
2. **The contract is sacred.** Any change to `AgentInput`/`AgentAction` touches
   `shared/actions.schema.json`, `agent/app/schema.py`, and `web/src/lib/types.ts` in one
   commit (ADR-012).
3. **No dead code, no commented-out code, no TODO without an owner-context sentence.**
4. **Secrets never enter the repo.** Keys live in `.env` (gitignored); `.env.example` documents
   every variable. Never print keys in logs or errors.
5. **Comments explain *why*, not *what*.** A comment earns its place by stating a constraint
   the code can't show (e.g. "gemini-flash-lite hangs on function_calling — keep off the
   allowlist").

## Python (`agent/`)

**Tooling (enforced, config in `agent/pyproject.toml`):**
- `ruff` — lint **and** format. No debates; the formatter wins.
- `mypy` — every function fully annotated; `Any` is a code smell that needs a justifying comment.
- `pytest` (+ `pytest-asyncio`) — tests must pass **offline** (LLM/vision paths behind flags
  like `vision_enabled=False`; fakes over network calls).

**Conventions:**
- Python 3.11+ syntax: `X | None` over `Optional[X]`, builtin generics (`list[str]`), `match`
  where it clarifies routing logic.
- **Pydantic v2 models for every boundary** (API request/response, LLM structured output,
  plan types). Internal-only data may use `dataclass`/`TypedDict`.
- **Async all the way down** in request paths: SQLAlchemy async, async LLM calls, `astream`
  from the engine. Never call blocking I/O in a route; CPU-ish work (Pillow render) stays
  small or moves behind `run_in_executor` when it grows.
- **Layering:** routes (`main.py`/`api/`) → graph/tools/repo → models. Routes never touch the
  ORM directly (go through `db/repo.py`); graph nodes never import FastAPI.
- **Nodes are functions over `AgentState`** returning deltas; keep them engine-agnostic and
  unit-testable in isolation.
- Errors: raise specific exceptions; convert to HTTP errors only at the route layer; the SSE
  stream ends with a typed `error` event, never a half-closed socket.
- Logging: `logging` module, structured-ish messages with session/run ids; no `print`.
- Naming: `snake_case` modules mirroring their responsibility (`parse_sql.py`,
  `critic_vision.py`); test files `test_<module>.py` mirroring source layout.

## TypeScript (`web/`)

**Tooling:** `tsc --noEmit` (strict) + `oxlint` must be clean.

**Conventions:**
- The client is **thin by policy**: `lib/` holds the only logic (transport, apply, api,
  session) — no business rules, no layout math. If you're computing diagram geometry in TS,
  stop and move it server-side (ADR-001, placement rules in
  [03-folder-structure.md](./03-folder-structure.md)).
- `type` over `interface` for contract mirrors; discriminated unions for `AgentAction`
  (switch with exhaustiveness check in `applyActions.ts`).
- Unknown action types are **ignored, never fatal** — forward compatibility (ADR-012).
- React: function components, hooks, no state library; split `App.tsx` into `components/`
  when it passes ~400 lines.
- Styling: design tokens in `index.css` (light + dark) — never hardcode a color in a
  component; add a token.
- tldraw specifics worth remembering: v5 labels use `richText` + `toRichText`; arrows bind via
  `start/end` VecModel; page-space math via `editor.getShapePageBounds`.

## Testing policy

| Layer | What must be tested | How |
|---|---|---|
| Parsers (`tools/`) | Grammar coverage + malformed input | Pure pytest, table-driven |
| Layout | Geometry invariants (no overlaps at default scale, arrows bound) | Assert on emitted actions |
| Graph | Each input path end-to-end (SQL/OpenAPI/text), refine loop triggers & terminates | Engine-level tests, LLM faked |
| Critic | Geometry findings; loop bounds | Offline (`vision_enabled=False`) |
| API | Route contracts, SSE event sequence, snapshot round-trip | httpx/ASGI test client |
| Web | Type-safety of the contract mirror | `tsc` (no unit-test suite until logic justifies one) |

Rules: a bug fix ships with the test that would have caught it; LLM-dependent behavior is
covered by the **eval harness** (v1), not unit tests; never let the suite require network or
a key.

## Quality gates (definition of done for any PR/commit to `main`)

```bash
# agent
cd agent && ruff check . && ruff format --check . && mypy app && python -m pytest
# web
cd web && npx tsc --noEmit && npm run lint && npm run build
```

CI runs exactly these (`.github/ci.yml.pending` → `workflows/ci.yml` once the token has
`workflow` scope). Red gates = no merge, no exceptions.

## Git conventions

- **Conventional commits**, scoped: `feat(agent): …`, `fix(web): …`, `chore(ci): …`,
  `docs: …` — matches existing history.
- Small commits, each leaving gates green; contract changes isolated in their own commit.
- `main` is deployable at all times. Feature branches for anything multi-day.
- Never commit: `.env`, `*.db`, caches, editor state. (Check `.gitignore` covers new artifacts.)
