"""SQLAlchemy models — sessions, snapshots, and run analytics.

Dev uses SQLite (`sqlite+aiosqlite`); the same models run on Postgres in prod by
swapping `DATABASE_URL` (see app/db/engine.py).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="Untitled")
    # Latest tldraw store snapshot (JSON), so a reload restores the canvas.
    snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Message(Base):
    """One turn in a session's conversation.

    A session is a conversation *and* the canvas it produced, so reopening one restores
    both. The assistant's turn is not prose: `activity` holds the run's trace (the spec it
    wrote, the plan it validated, what the Critic found) as JSON, and the UI replays that
    into the same blocks the user watched stream the first time.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # "user" | "assistant"
    text: Mapped[str] = mapped_column(Text, default="")
    activity: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON run trace
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Run(Base):
    """One agent run — for eval/analytics (input kind, shapes, iterations)."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"))
    input_kind: Mapped[str] = mapped_column(String(20), default="text")
    shape_count: Mapped[int] = mapped_column(Integer, default=0)
    iterations: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
