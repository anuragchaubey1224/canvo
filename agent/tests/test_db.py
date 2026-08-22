"""Persistence roundtrip — repository layer against an in-memory SQLite."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import repo
from app.db.models import Base


async def _scenario():
    # StaticPool keeps a single connection so the :memory: DB survives across calls.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as db:
        session = await repo.create_session(db, title="Shop schema")
        assert session.id and session.snapshot is None

        saved = await repo.save_snapshot(db, session.id, '{"shapes": 3}')
        assert saved is not None and saved.snapshot == '{"shapes": 3}'

        loaded = await repo.get_session(db, session.id)
        assert loaded is not None and loaded.snapshot == '{"shapes": 3}'

        run = await repo.record_run(
            db, user_id=None, session_id=session.id, input_kind="sql", shape_count=3, iterations=1
        )
        assert run.id is not None and run.input_kind == "sql"

        assert await repo.save_snapshot(db, "does-not-exist", "{}") is None

    await engine.dispose()


def test_persistence_roundtrip():
    asyncio.run(_scenario())
