"""Async engine + session factory. SQLite for dev, Postgres via DATABASE_URL for prod."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models import Base

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _db_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./canvo.db")


def engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(_db_url())
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(engine(), expire_on_commit=False)
    return _sessionmaker


async def init_db() -> None:
    """Create tables if missing (dev convenience; Alembic owns prod migrations)."""
    async with engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


def _add_missing_columns(conn) -> None:
    """Add columns that `create_all` can't, because the table already exists.

    `create_all` only creates *missing tables* — it never alters an existing one, so a
    developer with diagrams already on disk would otherwise get "no such column: user_id"
    with no hint why. This is a stopgap for local databases and is deliberately limited to
    nullable additive columns; **Alembic owns real migrations** and this should be deleted
    the moment it exists.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(conn)
    if "sessions" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("sessions")}
    if "user_id" not in existing:
        conn.execute(text("ALTER TABLE sessions ADD COLUMN user_id VARCHAR(36)"))


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yields a request-scoped session."""
    async with session_factory()() as db:
        yield db
