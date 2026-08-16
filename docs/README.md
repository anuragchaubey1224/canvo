# Canvo — Engineering & Product Documentation

Canvo is an AI-native diagramming product: an infinite canvas where a multi-tool agent turns
**real inputs** (a PRD, an OpenAPI spec, a SQL schema, code, or plain text) into live, editable
diagrams — and self-corrects them. It is built to compete directly with **Eraser.io** ($15/user/mo)
on quality, while being dramatically cheaper to run and to buy.

This folder is the single source of truth for how we build, decide, and ship.

| Doc | What it covers |
|---|---|
| [00-product-vision.md](./00-product-vision.md) | Positioning vs Eraser.io, target users, pricing strategy, feature parity map |
| [01-architecture.md](./01-architecture.md) | System architecture, data flow, the agent graph, streaming contract |
| [02-tech-stack.md](./02-tech-stack.md) | Chosen stack with rationale and monthly cost model |
| [03-folder-structure.md](./03-folder-structure.md) | Current and target repo layout, where new code goes |
| [04-roadmap.md](./04-roadmap.md) | Phased roadmap from today's codebase to a paid product |
| [05-design-decisions.md](./05-design-decisions.md) | Architecture Decision Records (ADRs) — what we chose and why |
| [06-code-style.md](./06-code-style.md) | Python & TypeScript conventions, quality gates, testing policy |
| [07-deployment.md](./07-deployment.md) | Deployment strategy, environments, cost controls, scaling path |
| [08-ai-features.md](./08-ai-features.md) | The AI feature set: agent pipeline, model strategy, cost per generation, evals |

## Ground rules (read before contributing)

1. **The engineering lives in Python.** `web/` (tldraw client) stays thin — it applies streamed
   actions and handles UX. All reasoning, parsing, layout, and self-correction lives in `agent/`.
2. **One contract.** Client and server communicate only through the `AgentInput` → streamed
   `AgentAction[]` contract (`agent/app/schema.py` ↔ `web/src/lib/types.ts`, mirrored from
   `shared/actions.schema.json`). Never let either side grow private knowledge of the other.
3. **Deterministic first, LLM second.** If an input can be parsed (SQL, OpenAPI), we parse it —
   zero tokens, zero latency, zero hallucination. The LLM handles only what parsing cannot.
4. **Every merge passes the gates.** ruff + mypy + pytest on the agent; tsc + lint on the web.
5. **Cost is a feature.** Every feature design must state its per-use LLM cost. See
   [08-ai-features.md](./08-ai-features.md) for the cost model.
