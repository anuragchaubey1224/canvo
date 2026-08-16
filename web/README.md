# Canvo Web (tldraw canvas client)

A **thin** React + Vite client built directly on the **tldraw SDK**. It sends input to the Python
agent-service and applies the streamed `AgentAction`s onto the canvas. The engineering lives in
`agent/`; this stays intentionally minimal (PLAN.md — "keep `web/` thin").

> Note: we use the tldraw **SDK** directly (not a fork of `tldraw/agent-template`). Bending the
> template's Cloudflare-Worker protocol to our Python contract was more work and more risk than a
> ~50-line action-apply layer we own. Same canvas, our contract stays central.

## Layout

```
web/src/
├── App.tsx              # input panel + <Tldraw> canvas; streams + applies actions
├── lib/
│   ├── types.ts         # mirror of the service contract (AgentAction, AgentInput)
│   ├── transport.ts     # POST /agent/stream, parse SSE
│   └── applyActions.ts  # AgentAction → tldraw shapes (geo boxes + bound arrows)
└── index.css            # minimal layout (polish comes later)
```

## Run

```bash
# 1) start the agent (separate terminal)
cd ../agent && source .venv/bin/activate && uvicorn app.main:app --port 8000

# 2) start the web client
npm install
npm run dev          # http://localhost:5173
```

Paste a SQL schema (a sample is pre-filled) and hit **Generate** — table boxes + foreign-key arrows
stream onto the canvas. Point at a different agent URL with `VITE_AGENT_URL`.

## Status

Spike: SQL → ERD renders end-to-end. UI is deliberately bare; design polish, more input types, and
live-streaming affordances land later.
