"""Repository layer — all DB access goes through here (no ORM in routes)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run, Session


async def create_session(db: AsyncSession, title: str = "Untitled") -> Session:
    obj = Session(id=uuid.uuid4().hex, title=title)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get_session(db: AsyncSession, session_id: str) -> Session | None:
    return await db.get(Session, session_id)


async def save_snapshot(db: AsyncSession, session_id: str, snapshot: str) -> Session | None:
    obj = await db.get(Session, session_id)
    if obj is None:
        return None
    obj.snapshot = snapshot
    await db.commit()
    await db.refresh(obj)
    return obj


async def record_run(
    db: AsyncSession, session_id: str, input_kind: str, shape_count: int, iterations: int
) -> Run:
    run = Run(
        session_id=session_id,
        input_kind=input_kind,
        shape_count=shape_count,
        iterations=iterations,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run
