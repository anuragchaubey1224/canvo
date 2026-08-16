"""Canvo agent-service — FastAPI entrypoint.

Phase 0 exposes:
  - GET  /health        service status
  - POST /agent/stream  runs the LangGraph Planner→Drawer→Critic graph and
                        streams AgentActions to the tldraw client (SSE).
"""
from __future__ import annotations

import asyncio
import json

from dotenv import load_dotenv

load_dotenv()  # read agent/.env (API keys, provider config) before anything uses it

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.graph.build import graph
from app.schema import AgentInput

app = FastAPI(title="Canvo Agent Service", version="0.0.1")

# Phase 0: open CORS for local dev. TODO: lock to the web origin before deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "canvo-agent", "version": "0.0.1"}


@app.post("/agent/stream")
async def agent_stream(payload: AgentInput):
    """Run the graph and stream each canvas action as a Server-Sent Event."""

    async def event_gen():
        state = {
            "user_message": payload.message,
            "payload": payload.payload,
            "input_kind": payload.input_kind,
            "canvas_context": payload.canvas_context,
            "iterations": 0,
            "cost_usd": 0.0,
        }

        # Phase 0: run the graph to completion, then stream the actions.
        # TODO: switch to `graph.astream(...)` to emit shapes node-by-node as
        # the Drawer produces them (true incremental live-draw).
        result = await graph.ainvoke(state)

        for action in result.get("actions", []):
            yield f"data: {action.model_dump_json()}\n\n"
            await asyncio.sleep(0.15)  # simulate live streaming

        yield f"event: done\ndata: {json.dumps({'iterations': result.get('iterations', 0)})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
