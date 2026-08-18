"""SQLAlchemy models — sessions, snapshots, and run analytics.

Dev uses SQLite (`sqlite+aiosqlite`); the same models run on Postgres in prod by
swapping `DATABASE_URL` (see app/db/engine.py).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    """An account. Email is the identity; `email` is stored already lower-cased and
    stripped so the UNIQUE index is the case-insensitivity guarantee, rather than hoping
    every call site remembers to normalise."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Whether the address has been confirmed. Signup does not block on it — an unverified
    # account still works — but it is what lets us trust the inbox for recovery later.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuthToken(Base):
    """A single-use token behind an emailed link — password reset, or address confirmation.

    Keyed by the SHA-256 of the token like a session, and `used_at` is what makes it
    single-use: a link that has worked once is spent, so forwarding it, or a mail scanner
    following it, hands nobody a second chance. `purpose` is checked on redemption so a
    verification link can never be replayed as a password reset.
    """

    __tablename__ = "auth_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(16), index=True)  # "reset" | "verify"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthSession(Base):
    """A logged-in browser.

    The row is keyed by the SHA-256 of the token, never the token itself: a leaked
    database then contains nothing anyone can log in with. Expiry is stored rather than
    inferred so a session can be cut short (logout, password change) by deleting the row.
    """

    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Nullable so diagrams created before accounts existed still load; every new one is
    # owned, and the read paths filter on it.
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="Untitled")
    # Latest tldraw store snapshot (JSON), so a reload restores the canvas.
    snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The DiagramPlan behind that canvas, as JSON. This is what a follow-up prompt edits:
    # the shapes are derived output, and re-deriving intent from them would be guesswork.
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)
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
