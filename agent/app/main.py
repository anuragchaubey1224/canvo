"""Canvo agent-service — FastAPI entrypoint.

Phase 0 exposes:
  - GET  /health        service status
  - POST /agent/stream  runs the LangGraph Planner→Drawer→Critic graph and
                        streams AgentActions to the tldraw client (SSE).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import current_user
from app.auth.router import router as auth_router
from app.db import repo
from app.db.engine import get_db, init_db
from app.db.models import User
from app.graph.build import graph
from app.schema import AgentInput

# Read agent/.env (API keys, provider config) before any request resolves LLM config.
load_dotenv()

# Shapes are staggered onto the canvas so a diagram appears to draw itself. It's a total
# budget shared by the whole diagram — a per-shape constant makes big diagrams feel slow
# for no reason, and the server is already done by then.
_DRAW_BUDGET = 1.2  # seconds for the whole diagram
_MAX_STAGGER = 0.06  # ceiling for a small one, so it still reads as drawing


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()  # dev convenience; Alembic owns prod migrations
    yield


app = FastAPI(title="Canvo Agent Service", version="0.0.1", lifespan=lifespan)

# Session cookies require an explicit origin allow-list: a browser refuses to send
# credentials to a wildcard origin, and accepting "*" with credentials would let any site
# read a signed-in user's diagrams. Set ALLOWED_ORIGINS in production.
_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "canvo-agent", "version": "0.0.1"}


class SnapshotIn(BaseModel):
    snapshot: str


class TitleIn(BaseModel):
    title: str


class MessageIn(BaseModel):
    role: str  # "user" | "assistant"
    text: str = ""
    activity: dict | None = None  # the run trace: spec, plan, critique passes


# Every route below takes `current_user`. Identity is a parameter, not ambient state, so
# a route that forgets to scope its query has no user id to filter by and fails review
# rather than quietly serving someone else's diagrams.
@app.post("/sessions")
async def create_session(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Create a diagram owned by the caller."""
    s = await repo.create_session(db, user_id=user.id)
    return {"id": s.id, "title": s.title}


@app.get("/sessions")
async def list_sessions(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Conversation history — a session is a chat and the canvas it produced."""
    return [
        {
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
            "messages": n,
            "has_canvas": bool(s.snapshot),
        }
        for s, n in await repo.list_sessions(db, user.id)
    ]


@app.patch("/sessions/{session_id}")
async def rename_session(
    session_id: str,
    body: TitleIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await repo.rename_session(db, session_id, body.title, user.id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"id": s.id, "title": s.title}


@app.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    if not await repo.delete_session(db, session_id, user.id):
        raise HTTPException(status_code=404, detail="session not found")
    return {"ok": True}


@app.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    return [
        {
            "id": m.id,
            "role": m.role,
            "text": m.text,
            "activity": json.loads(m.activity) if m.activity else None,
            "created_at": m.created_at.isoformat(),
        }
        for m in await repo.list_messages(db, session_id, user.id)
    ]


@app.post("/sessions/{session_id}/messages")
async def post_message(
    session_id: str,
    body: MessageIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    activity = json.dumps(body.activity) if body.activity is not None else None
    m = await repo.add_message(db, session_id, body.role, body.text, activity, user.id)
    if m is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"id": m.id, "created_at": m.created_at.isoformat()}


@app.get("/sessions/{session_id}/snapshot")
async def get_snapshot(
    session_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    s = await repo.get_session(db, session_id, user.id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"snapshot": s.snapshot}


@app.put("/sessions/{session_id}/snapshot")
async def put_snapshot(
    session_id: str,
    body: SnapshotIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await repo.save_snapshot(db, session_id, body.snapshot, user.id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"ok": True, "updated_at": s.updated_at.isoformat()}


@app.post("/agent/stream")
async def agent_stream(payload: AgentInput, user: User = Depends(current_user)):
    """Run the graph and stream the run as Server-Sent Events.

    Consumes `graph.astream(...)` (our engine yields `(node, update)` per step), so the
    whole reasoning chain is observable as it happens:

      `spec`     the Specifier's brief — what it understood, and what it had to assume
      `plan`     the graph it produced + what the validator found/repaired
      `critique` one per Critic visit (found overlaps → widened spacing → clean)
      actions    the FINAL, self-corrected diagram, streamed as one clean draw
      `done`     run summary

    Streaming the spec and plan first is what makes the assumptions correctable: the user
    reads what the model filled in before judging the picture it drew.
    """

    async def event_gen():
        state = {
            "user_message": payload.message,
            "payload": payload.payload,
            "input_kind": payload.input_kind,
            "canvas_context": payload.canvas_context,
            "vision_enabled": (True if payload.enable_vision is None else payload.enable_vision),
            "spec_enabled": (True if payload.enable_spec is None else payload.enable_spec),
            # BYOK / per-request model override — used for this request only, never persisted.
            "llm_override": (payload.llm.model_dump(exclude_none=True) if payload.llm else None),
            "layout_params": {"gap_scale": 1.0},
            "iterations": 0,
            "cost_usd": 0.0,
        }

        started = time.perf_counter()
        drawn = 0
        passes: list[dict] = []

        async def draw(actions: list) -> AsyncIterator[str]:
            """Stream one diagram. The stagger is a total budget, not a per-shape delay:
            at a fixed 0.12s a 40-shape diagram spent five seconds dribbling onto a canvas
            the server had already finished computing."""
            delay = min(_MAX_STAGGER, _DRAW_BUDGET / max(1, len(actions)))
            for action in actions:
                yield f"data: {action.model_dump_json()}\n\n"
                await asyncio.sleep(delay)

        async for node, out in graph.astream(state):
            if not out:
                continue
            # Reveal the diagram the moment the Drawer has one, rather than holding it
            # back until the vision Critic has finished looking at it — that pass costs
            # ~10s and the user was staring at an empty canvas for all of it. A refine
            # replaces the drawing in place, announced by `redraw`.
            if node == "drawer" and out.get("actions"):
                if drawn:
                    yield "event: redraw\ndata: {}\n\n"
                async for chunk in draw(out["actions"]):
                    yield chunk
                drawn = len(out["actions"])
            if node == "specifier" and out.get("spec"):
                spec = out["spec"]
                yield (
                    "event: spec\ndata: "
                    + json.dumps(
                        {
                            "title": spec.title,
                            "diagram_type": spec.diagram_type,
                            "components": spec.component_names,
                            "flow_steps": len(spec.flow_steps),
                            "phases": spec.phases,
                            "assumptions": spec.assumptions,
                            "raw": spec.raw,
                        }
                    )
                    + "\n\n"
                )
                await asyncio.sleep(0.05)
            if node == "planner" and out.get("plan_report"):
                yield "event: plan\ndata: " + json.dumps(out["plan_report"]) + "\n\n"
                await asyncio.sleep(0.05)
            if node == "critic" and out.get("critique"):
                c = out["critique"]
                passes.append(c)
                yield (
                    "event: critique\ndata: "
                    + json.dumps(
                        {
                            "pass": len(passes),
                            "has_issues": c.get("has_issues", False),
                            "needs_refine": c.get("needs_refine", False),
                            "source": c.get("source"),
                            "summary": c.get("summary"),
                            "gap_scale": c.get("gap_scale"),
                            "issue_count": len(c.get("issues", [])),
                            "issues": c.get("issues", []),
                        }
                    )
                    + "\n\n"
                )
                await asyncio.sleep(0.05)

        refined = len(passes) > 1
        yield (
            "event: done\ndata: "
            + json.dumps(
                {
                    "iterations": len(passes),
                    "refined": refined,
                    "shapes": drawn,
                    "critic_source": passes[-1].get("source") if passes else None,
                    "final_clean": bool(passes) and not passes[-1].get("needs_refine", False),
                    # Wall clock for the whole run. Surfaced so slow stages are visible
                    # instead of guessed at — every stage here is one network round trip.
                    "elapsed_s": round(time.perf_counter() - started, 2),
                }
            )
            + "\n\n"
        )

    return StreamingResponse(event_gen(), media_type="text/event-stream")
