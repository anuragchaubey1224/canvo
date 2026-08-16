"""Canvo agent-service — FastAPI entrypoint.

Phase 0 exposes:
  - GET  /health        service status
  - POST /agent/stream  runs the LangGraph Planner→Drawer→Critic graph and
                        streams AgentActions to the tldraw client (SSE).
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import repo
from app.db.engine import get_db, init_db
from app.graph.build import graph
from app.schema import AgentInput

# Read agent/.env (API keys, provider config) before any request resolves LLM config.
load_dotenv()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()  # dev convenience; Alembic owns prod migrations
    yield


app = FastAPI(title="Canvo Agent Service", version="0.0.1", lifespan=lifespan)

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


class SnapshotIn(BaseModel):
    snapshot: str


@app.post("/sessions")
async def create_session(db: AsyncSession = Depends(get_db)):
    """Create a session; the client stores its id and autosaves snapshots to it."""
    s = await repo.create_session(db)
    return {"id": s.id, "title": s.title}


@app.get("/sessions/{session_id}/snapshot")
async def get_snapshot(session_id: str, db: AsyncSession = Depends(get_db)):
    s = await repo.get_session(db, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"snapshot": s.snapshot}


@app.put("/sessions/{session_id}/snapshot")
async def put_snapshot(session_id: str, body: SnapshotIn, db: AsyncSession = Depends(get_db)):
    s = await repo.save_snapshot(db, session_id, body.snapshot)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"ok": True, "updated_at": s.updated_at.isoformat()}


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
