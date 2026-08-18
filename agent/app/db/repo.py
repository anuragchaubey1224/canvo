"""Repository layer — all DB access goes through here (no ORM in routes)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, Run, Session

# A provisional conversation title taken from the first prompt. The client replaces it
# with the spec's own title once the Spec Writer has one, so the name sharpens as the
# run progresses rather than staying "Untitled" until the user renames it by hand.
_TITLE_MAX = 60


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


async def list_sessions(db: AsyncSession, limit: int = 50) -> list[tuple[Session, int]]:
    """Conversations for the history menu, most recently touched first, with turn counts."""
    counts = (
        select(Message.session_id, func.count(Message.id).label("n"))
        .group_by(Message.session_id)
        .subquery()
    )
    rows = await db.execute(
        select(Session, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.session_id == Session.id)
        .order_by(Session.updated_at.desc())
        .limit(limit)
    )
    return [(session, int(n)) for session, n in rows.all()]


async def rename_session(db: AsyncSession, session_id: str, title: str) -> Session | None:
    obj = await db.get(Session, session_id)
    if obj is None:
        return None
    obj.title = title.strip()[:_TITLE_MAX] or "Untitled"
    await db.commit()
    await db.refresh(obj)
    return obj


async def delete_session(db: AsyncSession, session_id: str) -> bool:
    obj = await db.get(Session, session_id)
    if obj is None:
        return False
    await db.execute(delete(Message).where(Message.session_id == session_id))
    await db.execute(delete(Run).where(Run.session_id == session_id))
    await db.delete(obj)
    await db.commit()
    return True


async def add_message(
    db: AsyncSession, session_id: str, role: str, text: str, activity: str | None = None
) -> Message | None:
    session = await db.get(Session, session_id)
    if session is None:
        return None
    msg = Message(session_id=session_id, role=role, text=text, activity=activity)
    db.add(msg)
    # Keep the conversation at the top of the history list, and give an unnamed one a
    # working title from the first thing the user actually asked for.
    session.updated_at = datetime.now(UTC)
    if role == "user" and session.title in ("", "Untitled") and text.strip():
        session.title = " ".join(text.split())[:_TITLE_MAX]
    await db.commit()
    await db.refresh(msg)
    return msg


async def list_messages(db: AsyncSession, session_id: str) -> list[Message]:
    rows = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.id)
    )
    return list(rows.scalars().all())


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
