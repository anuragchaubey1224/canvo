"""Conversation persistence — messages, titles, history ordering (in-memory SQLite)."""

from __future__ import annotations

import asyncio
import json

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import repo
from app.db.models import Base


async def _db():
    # StaticPool keeps a single connection so the :memory: DB survives across calls.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _messages_roundtrip():
    engine, sm = await _db()
    async with sm() as db:
        session = await repo.create_session(db)
        assert session.title == "Untitled"

        # The first prompt names the conversation — nobody wants a list of "Untitled".
        await repo.add_message(db, session.id, "user", "Draw a JWT authentication workflow")
        named = await repo.get_session(db, session.id)
        assert named is not None and named.title == "Draw a JWT authentication workflow"

        trace = {"spec": {"title": "JWT Auth"}, "plan": {"nodes": 12}}
        await repo.add_message(db, session.id, "assistant", "Drew 34 shapes", json.dumps(trace))

        stored = await repo.list_messages(db, session.id)
        assert [m.role for m in stored] == ["user", "assistant"]
        assert json.loads(stored[1].activity)["plan"]["nodes"] == 12

        # A later prompt must not rewrite a title the conversation already earned.
        await repo.add_message(db, session.id, "user", "now add a rate limiter")
        again = await repo.get_session(db, session.id)
        assert again is not None and again.title == "Draw a JWT authentication workflow"
    await engine.dispose()


async def _history_and_lifecycle():
    engine, sm = await _db()
    async with sm() as db:
        owner = await repo.create_user(db, "owner@example.com", "hash")
        first = await repo.create_session(db, title="First", user_id=owner.id)
        second = await repo.create_session(db, title="Second", user_id=owner.id)
        await repo.add_message(db, second.id, "user", "hello")

        history = await repo.list_sessions(db, owner.id)
        assert {s.title for s, _ in history} == {"First", "Second"}
        counts = {s.title: n for s, n in history}
        assert counts["Second"] == 1 and counts["First"] == 0
        assert history[0][0].id == second.id  # most recently touched first

        renamed = await repo.rename_session(db, first.id, "  A much better name  ")
        assert renamed is not None and renamed.title == "A much better name"

        assert await repo.delete_session(db, second.id) is True
        assert await repo.get_session(db, second.id) is None
        assert await repo.list_messages(db, second.id) == []  # its turns go with it
        assert await repo.delete_session(db, "does-not-exist") is False

        assert await repo.add_message(db, "does-not-exist", "user", "x") is None
    await engine.dispose()


def test_messages_roundtrip():
    asyncio.run(_messages_roundtrip())


def test_history_listing_and_lifecycle():
    asyncio.run(_history_and_lifecycle())
