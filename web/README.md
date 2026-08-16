# Canvo Web (tldraw canvas client)

**Placeholder — added in the Phase-0 spike (PLAN.md §11).**

## Next step

Fork the tldraw agent starter kit into this folder and get it running *as-is* first, so we
learn the client↔server contract before swapping in our Python brain:

```bash
# from repo root
npm create tldraw@latest            # choose the "agent" starter kit
# or: git clone https://github.com/tldraw/agent-template web
```

Then:

1. Run it unchanged with an Anthropic key (`.dev.vars`) — type a prompt, watch it draw.
2. Note exactly what the client sends (message + canvas context) and what actions it applies.
3. Point the client's transport at our Python service (`POST http://127.0.0.1:8000/agent/stream`,
   SSE) for a single "create shapes" path — see `shared/README.md` for the contract.

What we **keep** from the template: the canvas, action-apply, and visual-context gathering
(screenshot + shape data). What we **replace**: the server/brain → `agent/` (Python + LangGraph).
