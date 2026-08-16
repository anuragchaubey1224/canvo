# Sketchpilot — Conversational Agentic Canvas (Solidified Plan v2)

> Working name: **Sketchpilot** (placeholder — Canvo / Muse / Draftsman bhi options).
> One-liner: *"An infinite canvas where you talk (or type) and a LangGraph-orchestrated
> multi-agent system (Planner → Drawer → Critic) draws, refines, and self-corrects diagrams
> live — with full tracing, evals, and an MCP interface."*

**Positioning goal:** Yeh project ka #1 kaam = *agentic AI engineer* wali jobs ke liye ek
undeniable proof-of-work banana. Isliye v2 mein architecture deliberately **hybrid** hai:
canvas/rendering tldraw handle karega, par **agent ka "brain" ek alag Python + LangGraph
service** mein hai — taaki recruiter ke saare agentic-infra checkboxes (orchestration,
observability, evals, guardrails, MCP) explicitly tick ho.

---

## 0. v1 → v2 mein kya badla (aur kyun)

| # | v1 (original plan) | v2 (yeh) | Kyun |
|---|---|---|---|
| 1 | Orchestration tldraw ke `modes`/`schedule` ke andar (TS, Cloudflare Worker) | **Alag Python FastAPI + LangGraph agent-service** | "Agentic AI engineer" roles Python-stack (LangGraph/LangChain/MCP) maangte hain. Framework ke andar chhupa loop resume par dikhta nahi. |
| 2 | Eval "nice-to-have" section | **Eval-driven development — core deliverable** | Job listings mein eval/judge-calibration explicitly maanga jaata hai. Yehi senior signal. |
| 3 | Observability mention nahi | **Langfuse/LangSmith tracing — har node par token/cost/latency** | Interviewer sabse pehle yehi poochhta hai: "how do you debug/measure an agent?" |
| 4 | MCP nahi tha | **Agent ko MCP server ke roop mein bhi expose karna** | 2026 ka sabse hot signal; prior-art (`tldraw-skill`) ke "agent skill" angle ko proper MCP se beat karta hai. |
| 5 | Guardrails halke | **Explicit safety layer: cost caps, iteration caps, prompt-injection defense, schema validation** | "Autonomy control" / "safety layer" job requirement. |
| 6 | Persistence CF KV/Supabase optional | **Supabase (Postgres) — sessions + snapshots + trace links** | Portable, Python-idiomatic, worker-lock-in avoid. |

**Kya same raha (verified, still correct):** tldraw agent template real hai, canvas + client-side
action-apply + visual-context (screenshot + shape data) production-ready deta hai — hum use *reuse*
karenge, sirf server-side brain replace karenge. Voice-first + conversational + live-streaming +
self-correction abhi bhi asli differentiators hain (neeche §2 prior-art dekho).

---

## 1. Product vision & positioning

- **Kya hai:** ek infinite canvas jisme aap bol/type kar ke bologe "draw a login flow for an
  e-commerce app", aur ek multi-agent system live canvas par shapes draw karta hai — aap beech mein
  bol kar edit karwate ho ("make the DB node bigger", "add a payment step after cart"). Agent
  canvas ka current state dekhta hai (screenshot + structured shapes) aur khud galtiyan sudhaarta hai.
- **Differentiation (resume/product ka core):**
  1. **Voice-first, conversational, continuous** — competitors mostly ek-shot "text → diagram".
     Yahan multi-turn back-and-forth; agent har turn canvas state ko re-read karta hai (grounding).
  2. **Explicit multi-agent graph (Planner → Drawer → Critic)** — LangGraph state machine, conditional
     edges, bounded refine loop. Critic screenshot dekh ke overlaps/missing steps pakadta hai (vision self-correction).
  3. **Measured, not vibes** — eval harness + before/after critic table + live tracing dashboard.
- **Kiske liye:** engineers/PMs jo architecture/flow jaldi sketch karna chahte hain bina mouse ghise.

---

## 2. Prior-art & competitive landscape (jaan lo, phir differentiate karo)

Research se ye mila — inko README/demo mein *acknowledge* karo aur clearly batao aap kya extra dete ho:

| Project | Kya karta hai | Kya NAHI karta (aapka gap = differentiator) |
|---|---|---|
| **`Agents365-ai/tldraw-skill`** (117★, MIT) | NL → `.tldr` diagrams, 6 presets, vision self-check (≤2 rounds), semantic palette | Sirf text-prompt **skill** hai — **no voice, no live-streaming canvas, no hosted conversational app, no eval/observability infra** |
| **tldraw `agent-template`** (official) | Canvas + agent framework (modes/actions/parts), TS + CF Worker | Single-agent by default; **no explicit multi-agent graph, no Python/LangGraph, no evals/tracing, no voice** |
| **Excalidraw / Eraser AI** | Text → diagram, polished | One-shot generation, **no conversational refine loop, no self-correcting critic, closed** |

> **Takeaway:** Idea validated hai (log ise banate hain), par *aapka slice bacha hua hai* —
> **voice + continuous conversation + explicit observable multi-agent graph + eval-driven + MCP**.
> Yeh combination kisi single competitor ke paas nahi. `tldraw-skill` ko duplicate mat karna
> (presets/vision-check woh already kar chuka); usse aage jao (live app + agentic infra).

---

## 3. Job-signal map — har feature ↔ 2026 "agentic AI engineer" requirement

Yeh table = plan ka "why". Har cheez ek hiring checkbox par map hoti hai. Interview mein yahi bolna hai.

| Job requirement (2026 listings se) | Project mein kahan | Resume/interview line |
|---|---|---|
| Multi-agent orchestration | LangGraph Planner→Drawer→Critic graph (§5) | "Designed a stateful multi-agent graph with bounded self-correction loops" |
| LLM tool-calling / structured outputs | Pydantic action schemas → Claude tool-use (§4, §5) | "Typed tool schemas; model output validated + sanitized before applying" |
| Observability / tracing | Langfuse (self-host) per-node token/cost/latency (§6) | "Full trace per run; debugged latency/cost from spans" |
| Evaluation / LLM-as-judge / judge calibration | Eval harness, 20 prompts, before/after critic (§6, §13) | "Eval-driven: critic loop lifted diagram-accuracy from X→Y%, measured" |
| Guardrails / autonomy control / prompt-injection defense | Safety layer (§6) | "Cost/iteration caps, injection-hardened prompts, schema-validated actions" |
| Memory / state management | Session + canvas + conversation memory (§7 data model) | "Stateful sessions; agent re-grounds on current canvas each turn" |
| MCP (Model Context Protocol) | Agent as MCP server (§6, v1) | "Exposed the diagramming agent over MCP for Claude Desktop/Cursor" |
| Voice agents | Web Speech → Whisper (Python) → TTS (§8) | "Voice-first multimodal interface with server-side transcription" |
| Latency/cost optimization | Prompt caching, small model for planner, streaming (§9) | "Prompt caching + model-tiering cut cost/latency ~N%" |
| Multimodal / vision grounding | Screenshot + shape data to Critic (§5) | "Vision-grounded critic caught layout errors text-only agents miss" |

> Agar aap in 10 mein se 7-8 genuinely build karke *numbers ke saath* dikha do — yeh project
> ek mid/senior agentic-AI role ke liye standout portfolio piece ban jaata hai.

---

## 4. Architecture (v2 — hybrid)

**Cut point:** tldraw ka **client** reuse karo (canvas, action-apply, visual-context gathering,
streaming render). tldraw ke **server (CF Worker)** ko drop karke **Python FastAPI + LangGraph**
se replace karo. Contract = ek chhota shared schema (actions + canvas-context), Zod client-side /
Pydantic server-side — dono ek hi spec se mirror.

```
┌──────────────────────────────────────────────────────────────────┐
│  Browser — tldraw client (React + TS + Vite)   [template se reuse] │
│  ┌──────────┐  ┌────────────────┐  ┌──────────────────────────┐    │
│  │ Voice/   │  │ Chat panel     │  │ tldraw canvas            │    │
│  │ type in  │─▶│ transcript +   │  │ (client applies actions, │    │
│  │          │  │ agent status   │  │  streams shapes live)    │    │
│  └──────────┘  └───────┬────────┘  └────────────▲─────────────┘    │
│    AgentInput = {message, canvasContext:        │ AgentAction[]    │
│      focusedShapes, blurryShapes, screenshot}   │ (create/update/  │
└─────────────────────────┬───────────────────────┴─delete/…)───────┘
                          │  POST /agent/stream  (SSE; WS in v1)
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  Python agent-service  (FastAPI)                                   │
│                                                                    │
│   LangGraph state graph:                                           │
│     ┌─────────┐   ┌────────┐   ┌────────┐                          │
│     │ PLANNER │──▶│ DRAWER │──▶│ CRITIC │──┐                       │
│     └─────────┘   └────────┘   └────┬───┘  │ conditional edge      │
│         ▲                           │       │ (issues? & iters<N)   │
│         └─────────── refine ────────┴───────┘                       │
│                                                                    │
│   • Claude tool-calling (Pydantic action schemas)                  │
│   • Prompt caching, model-tiering (Haiku planner / Sonnet drawer)  │
│   • Langfuse tracing on every node                                 │
│   • Guardrails: cost/iter caps, injection defense, schema validate │
│                                                                    │
│   MCP server (same graph exposed as an MCP tool) ────────────────▶ │  Claude Desktop /
└─────────────────────────┬──────────────────────────────────────────┘  Cursor (v1)
                          │
                          ▼
          Supabase (Postgres): sessions, snapshots, chat_turns, trace links
```

**Client↔server contract (the one thing to get right early):**
- `AgentInput` (client → server): `{ message, canvasContext: { focusedShapes[], blurryShapes[], screenshot(base64) }, sessionId }`
- `AgentAction[]` (server → client, streamed): create/update/delete/align/connect shapes — same shape
  ops the tldraw client already knows how to apply.
- **Define schema once** (JSON Schema or a `/shared/schema.json`), generate/mirror to Zod (client)
  and Pydantic (server). Add a contract test so drift breaks CI, not the demo.

**Transport:** SSE for MVP (simple, unidirectional stream of actions). Upgrade to **WebSocket** in
v1 for interrupt/barge-in during voice + bidirectional status.

**Why not keep the CF worker as a proxy?** Extra hop + second backend + TS lock-in, zero job-signal
upside. Client → Python directly (CORS) is simpler and more Python-resume-friendly.

---

## 5. The multi-agent graph (the differentiator, done idiomatically)

Implement as a **LangGraph `StateGraph`**. State object carries the whole run.

```python
class AgentState(TypedDict):
    user_message: str
    canvas_context: CanvasContext        # focused + blurry shapes + screenshot
    plan: Plan | None                    # structured nodes/edges/layout hint
    actions: list[AgentAction]           # what Drawer produced
    critique: Critique | None            # issues found by Critic
    iterations: int
    cost_usd: float
```

**Nodes:**
1. **Planner** — `intent + canvas_context → Plan(JSON)`. Canvas ko touch nahi karta. Cheap model
   (Haiku 4.5) chalega. Output: nodes, edges, layout hint.
2. **Drawer** — `Plan → AgentAction[]` via Claude tool-calling (Pydantic schemas). Actions client
   ko stream hote hain (live draw). Sonnet 5 (best tool-calling).
3. **Critic** — `screenshot + shape_data → Critique`. "Intent match? overlaps? missing steps?"
   Vision-grounded. Agar issues → correction actions; warna done. Sonnet 5 (ya hardest cases pe Opus).

**Edges / loop guard:**
- `Planner → Drawer → Critic`.
- Conditional edge from Critic: `if critique.has_issues and state.iterations < N and state.cost_usd < CAP → back to Drawer (or Planner for big misses); else END`.
- **N = 2–3** (config). Cost + latency guard. Har iteration Langfuse mein ek span.

**Model IDs (current, 2026):** `claude-haiku-4-5` (planner), `claude-sonnet-5` (drawer/critic),
`claude-opus-5` sirf hardest critique ke liye (optional). Prompt caching on for the static system/schema parts.

---

## 6. Agentic-infra layer (yeh section = job ka asli maal)

Yeh woh cheezein hain jo `tldraw-skill` aur zyadatar hobby projects mein NAHI hoti. Isi se aap alag dikhte ho.

### 6a. Observability — **Langfuse** (self-host, free, open-source) [+ LangSmith optional]
- Har LangGraph node → ek span. Capture: prompt, model, tokens, cost, latency, output.
- Full run trace: Planner→Drawer→Critic→refine, iteration count visible.
- README mein trace screenshot daalo — instant credibility. Interview mein isse live debug dikha do.

### 6b. Evaluation harness (see §13 for detail) — **core deliverable, not optional**
- 20 fixed prompts, LLM-as-judge for "intent match", structural metrics, before/after critic table.

### 6c. Guardrails / safety layer
- **Cost cap** per run (`cost_usd` in state; hard stop).
- **Iteration cap** (N≤3) — runaway loop se bachao.
- **Prompt-injection defense** — user text ko system instructions se strictly separate; user canvas
  content agent ke tool-permissions ko override na kar sake. Ek chhota red-team test set rakho.
- **Schema validation + sanitize** — model output ko apply karne se pehle Pydantic validate +
  `sanitizeAction` (invalid shape IDs, out-of-bounds coords drop/clamp).

### 6d. MCP server (v1 — high signal, low effort)
- Same LangGraph graph ko ek **MCP tool** (`draw_diagram`) ke roop mein expose karo (FastMCP/Python SDK).
- Result: Claude Desktop / Cursor se bhi diagram banwa sako. "I shipped an MCP server" = strong 2026 line.

### 6e. Memory / state
- **Session memory**: canvas snapshot (Supabase) — reload par wapas.
- **Conversation memory**: last-N turns to the graph (context window managed).
- **(Stretch) semantic memory**: past diagram patterns embed karke retrieve — RAG signal (vector DB).

### 6f. Provider abstraction + BYOK (bring your own key)
- **Ek provider layer** (`agent/app/llm.py`): Anthropic direct, **OpenRouter** (one key → many
  models), ya koi bhi **OpenAI-compatible** gateway. Model/provider swap = base_url + key change.
- **BYOK**: user apni khud ki key + provider **per-request** de sake (`AgentInput.llm`) — apne quota
  par chale, aapka bill nahi. Absent ho to server env default.
- **Security (must):** user-supplied key sirf us request ke liye use ho — **kabhi log/persist na ho**,
  hamesha HTTPS. (Ek acchi resume line: "multi-provider BYOK with per-request key isolation".)

---

## 7. Data model (Supabase / Postgres)

- `sessions` — id, user, created_at, title
- `snapshots` — session_id, tldraw store JSON, updated_at (autosave, debounced)
- `chat_turns` — session_id, role (user/planner/drawer/critic), content, tokens, cost, latency, timestamp
- `runs` — session_id, langfuse_trace_id, iterations, total_cost, verdict (for eval/analytics)
- (auth optional for MVP; Supabase Auth for v1 if publicly hosted)

---

## 8. Voice layer (Python fits perfectly)

- **MVP:** browser **Web Speech API** (`SpeechRecognition`) — free, instant. Push-to-talk; interim +
  final transcript chat panel mein. Type karna hamesha available (voice optional).
- **v1:** **Whisper** server-side (Python `faster-whisper` / OpenAI Whisper API) — accuracy + Hindi/
  Indian-English accents. (Python service mein already ho — natural fit.)
- **Stretch:** TTS reply ("Added the payment node") — full conversational feel. WebSocket + barge-in.

---

## 9. Tech stack (final v2 decisions)

| Layer | Choice | Why |
|---|---|---|
| Canvas / frontend | **tldraw SDK** (agent-template client, fork) — React + TS + Vite | Production canvas + action-apply + visual context; reuse, don't rebuild |
| **Agent service** | **Python + FastAPI + LangGraph** | Job-target stack; explicit observable orchestration |
| LLM | **Claude** — Sonnet 5 (drawer/critic), Haiku 4.5 (planner), Opus 5 (hard critique) | Best tool-calling + vision; model-tiering for cost |
| Provider layer | Anthropic direct · **OpenRouter** · OpenAI-compatible (+ **BYOK**) | Model flexibility; users can bring their own key/quota |
| Tool schemas | **Pydantic** (server) ↔ **Zod** (client), one shared spec | Typed, validated, contract-tested |
| Observability | **Langfuse** (self-host) [+ LangSmith optional] | Per-node tracing = interview gold |
| Evals | LangGraph run harness + LLM-as-judge (custom; RAGAS-style ideas) | Before/after numbers |
| Voice | Web Speech → Whisper (Python) → TTS | Free MVP → accurate v1 |
| Persistence | **Supabase (Postgres)** | Sessions + snapshots + run analytics |
| Transport | SSE (MVP) → WebSocket (v1) | Simple first, bidirectional later |
| MCP | FastMCP / Python MCP SDK | Expose agent as a tool |
| Deploy | Frontend: Vercel/Netlify · Agent: Fly.io/Railway/Render (Python) · DB: Supabase | Standard, portable |

---

## 10. Repo structure (monorepo)

```
sketchpilot/
├── web/                 # tldraw client (forked from agent-template client)
│   ├── src/canvas/      #   action-apply + visual-context (reuse)
│   ├── src/chat/        #   chat panel, voice input
│   └── src/transport/   #   SSE/WS client to Python service
├── agent/               # Python FastAPI + LangGraph service
│   ├── graph/           #   nodes: planner.py, drawer.py, critic.py; graph.py
│   ├── schema/          #   Pydantic action + context models
│   ├── guardrails/      #   caps, injection defense, sanitize
│   ├── mcp/             #   MCP server exposing the graph
│   ├── evals/           #   dataset + judge + runner + report
│   └── obs/             #   Langfuse setup
├── shared/              # one schema spec → Zod + Pydantic mirror + contract test
└── README.md            # architecture, trace screenshots, eval table, demo GIF
```

---

## 11. Feature scope (phased)

### Phase 0 — Spike (de-risk the integration FIRST)
- [ ] Fork tldraw `agent-template`, run **as-is** (TS worker), type→diagram working with Claude.
- [ ] Client↔server contract samjho: `AgentInput` + `AgentAction[]` exactly kya bhejte/aate hain.
- [ ] Monorepo set up (`web/` + `agent/` + `shared/`).

### MVP ("done" ka definition)
- [ ] Python FastAPI service khada; **ek** action path (create shapes) client se Python ko wire, SSE stream.
- [ ] LangGraph **Planner → Drawer** graph working (canvas actual mein banta hai).
- [ ] Agent canvas-state aware (edit existing, not just create fresh).
- [ ] Voice input (Web Speech) → same pipeline.
- [ ] Session persist (Supabase; reload par diagram wapas).
- [ ] Langfuse tracing on every node (basic).

### v1 (differentiation — yeh sell karta hai)
- [ ] **Critic node + refine loop** (vision self-correction, bounded N).
- [ ] Guardrails: cost/iter caps, injection defense, schema validate/sanitize.
- [ ] **Eval harness** + before/after-critic accuracy table (§13).
- [ ] Whisper voice upgrade; WebSocket transport.
- [ ] Diagram presets: flowchart, sequence, ER, architecture, mind-map.
- [ ] **MCP server** (`draw_diagram` tool).
- [ ] **BYOK**: provider abstraction (Anthropic / OpenRouter / OpenAI-compatible) + per-request user key.
- [ ] Export (PNG/SVG) + share link.

### Stretch (bonus resume points)
- [ ] Real-time multiplayer (tldraw sync).
- [ ] TTS reply + barge-in (full voice conversation).
- [ ] Semantic memory of past diagrams (vector DB → RAG signal).
- [ ] "Explain this diagram" reverse mode (canvas → text summary).
- [ ] A2A: second agent (e.g., a "reviewer" service) via agent-to-agent protocol.

---

## 12. Roadmap & timeline (solo, part-time — hybrid adds ~1 wk vs v1)

| Week | Goal |
|---|---|
| 1 | **Phase 0 spike.** Template run as-is, contract samjho, monorepo. |
| 2 | Python FastAPI service; port one action path; client→Python SSE for "create shapes". **(Riskiest — integration milestone.)** |
| 3 | LangGraph Planner→Drawer; canvas-state awareness; Supabase persist; Langfuse tracing. **MVP done.** |
| 4 | Critic node + refine loop; guardrails (caps, injection, sanitize); streaming polish. |
| 5 | Voice (Web Speech→Whisper), presets, export/share, WebSocket. |
| 6 | **Eval harness + before/after table**; MCP server; README + trace/eval screenshots + demo video; deploy. **v1 / portfolio-ready.** |
| 7+ | Stretch: multiplayer, TTS, semantic memory, A2A. |

> Full-time ho to ~3-4 hafte mein compress. **Rule:** Phase 0/integration ko rush mat karna —
> yahi poore project ka technical risk hai. Baaki sab uske upar predictable hai.

---

## 13. Eval harness (senior signal — build this properly)

- **Dataset:** 20 fixed prompts ("draw a 3-tier web architecture", "sequence diagram for OAuth login",
  "ER diagram for a blog", "state machine for an order", …). Store as `agent/evals/dataset.jsonl`.
- **Metrics per run:**
  - (a) shapes created vs expected (structural),
  - (b) **LLM-as-judge**: "does this diagram match the intent?" (0–1, calibrate judge on a few by hand),
  - (c) did Critic catch/fix a real error (labelled),
  - (d) iterations to converge,
  - (e) latency,
  - (f) cost per diagram.
- **Headline table — WITHOUT critic loop vs WITH critic loop:** accuracy X% → Y%. Yeh number README +
  resume + interview teeno mein use hota hai.
- **Judge calibration note:** ~5 examples hand-label karke judge se agreement check karo — "how do you
  trust your eval?" ka answer ready rahe.

---

## 14. Resume framing + interview prep

**Resume bullet (ready-to-use):**
> **Sketchpilot — Conversational Agentic Diagramming Canvas**
> Built a voice-driven infinite canvas where a **LangGraph** multi-agent system (Planner → Drawer →
> Critic) powered by **Claude** generates and **self-corrects** diagrams in real time. Python/FastAPI
> agent-service with **typed tool-calling** (Pydantic), **vision-grounded critique**, **prompt-injection
> guardrails**, and an **MCP** interface. Instrumented every node with **Langfuse** tracing and built an
> **eval harness** (LLM-as-judge) showing the self-correction loop lifted diagram accuracy **X%→Y%**.
> Stack: Python, FastAPI, LangGraph, Claude, tldraw/React-TS, Whisper, Supabase, Langfuse.

Checks: multi-agent orchestration ✓, tool-calling/structured output ✓, observability ✓, eval-driven ✓,
guardrails ✓, MCP ✓, voice/multimodal ✓, full-stack ✓.

**Interview questions ye grill karenge (answers pehle se ready rakho):**
- "Agent ko debug/measure kaise karte ho?" → Langfuse traces + eval harness dikhao.
- "Critic loop infinite kyun nahi hota?" → iteration + cost caps, conditional edge.
- "Prompt injection kaise handle kiya?" → separation + schema validate + red-team set.
- "Judge par bharosa kyun?" → hand-calibration + agreement metric.
- "Sonnet vs Haiku kaha aur kyun?" → model-tiering for cost/latency.
- "Ye `tldraw-skill` se alag kaise?" → voice + live app + observable graph + evals + MCP.

---

## 15. Risks & guardrails

- **Integration risk (BIGGEST, v2-specific)** — tldraw client ko custom Python backend se wire karna.
  *Mitigation:* Phase 0 mein template as-is chalao, contract samjho, PHIR swap. Ek action path se start.
- **Two-language / schema drift** — Zod vs Pydantic mismatch. *Mitigation:* one shared spec + contract test in CI.
- **Scope creep** — sabse bada silent killer. Ek angle (conversational + observable) par focus; presets/
  multiplayer baad mein. MVP ki checklist se bahar mat jao jab tak MVP done na ho.
- **LLM cost/latency** — critic N≤3, Haiku planner, prompt caching, stream.
- **Voice accuracy (accents)** — Web Speech → Whisper; type hamesha available.
- **"Just another AI diagram tool" perception** — README/demo mein multi-agent graph + voice +
  self-correction + traces + eval numbers ko loud karo. Yehi moat.
- **Don't reinvent canvas/collab** — tldraw pe raho; brain hi custom banao.
- **Don't duplicate `tldraw-skill`** — presets/vision-check woh kar chuka; aap live-app + infra layer do.

---

## 16. Immediate next steps

1. `git init` yeh repo, phir `web/` mein tldraw agent-template fork clone/copy karo.
   (`git clone https://github.com/tldraw/agent-template web` ya `npm create tldraw@latest`.)
2. Anthropic API key → `.dev.vars`, `npm install && npm run dev` — template **as-is** chala ke
   ek diagram type-prompt se banwao (pipeline samjho, contract note karo).
3. `agent/` mein FastAPI + LangGraph skeleton khada karo; `pip install langgraph langchain-anthropic
   fastapi uvicorn langfuse pydantic`. Ek dummy `/agent/stream` endpoint jo ek hardcoded action stream kare.
4. Client ke transport ko us endpoint pe point karo — **ek** shape create end-to-end chala do.
   (Yeh MVP ka spine hai; iske baad Planner/Drawer/Critic add karna incremental hai.)
5. Phir §12 Week-by-week follow karo.

---

*Plan v2 solidified 2026-08-16. Verified: tldraw agent-template (modes/actions/prompt-parts, CF Worker,
Anthropic/OpenAI/Google, `agent.schedule`/`interrupt`), prior-art `Agents365-ai/tldraw-skill` (117★),
2026 agentic-AI job requirements (LangGraph/MCP/observability/evals/guardrails). Direction: Python-heavy
agentic-AI roles, hybrid tldraw-client + Python/LangGraph agent-service.*
