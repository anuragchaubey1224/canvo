# Canvo Agent Service

Python + FastAPI + LangGraph service that plans, draws, and self-corrects diagrams for the
tldraw canvas client. This is the "brain" of Canvo.

## Layout

```
agent/
├── app/
│   ├── main.py           # FastAPI: /health, /agent/stream (SSE)
│   ├── schema.py         # Pydantic contract: AgentInput, CanvasContext, AgentAction
│   ├── guardrails.py     # cost/iteration caps (stubs; real safety layer in v1)
│   └── graph/
│       ├── state.py      # AgentState (LangGraph state)
│       ├── nodes.py      # planner / drawer / critic  (Phase-0 stubs)
│       └── build.py      # StateGraph wiring + bounded refine loop
├── requirements.txt
└── .env.example
```

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

- `GET  /health` → service status
- `POST /agent/stream` → runs the Planner→Drawer→Critic graph, streams `AgentAction` events (SSE)

## What's a stub right now

`nodes.py` produces a tiny hardcoded diagram so the full pipeline works without an API key.
Replacing each node with Claude tool-calling is the first "one by one" step — see `PLAN.md` §5.
