"""The generation allowance.

This is a cost boundary, not a UX nicety: everything it guards spends money, and the
endpoint behind it is reachable by anyone holding a session cookie. So the tests here are
about the ways a limit gets quietly defeated — deleting your work to get a refund, failing
on purpose, making a second account — rather than about the happy path.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import quota
from app.db import repo
from app.db.models import Base


@pytest.fixture
def env(monkeypatch):
    """Limits come from the environment, read per call — so a test sets them directly."""

    def set(user: int | None = None, daily: int | None = None):
        monkeypatch.setenv("FREE_RUN_LIMIT", "" if user is None else str(user))
        monkeypatch.setenv("DAILY_RUN_LIMIT", "" if daily is None else str(daily))

    return set


# --- the policy, in isolation -------------------------------------------------------------


def test_allows_until_the_limit_then_refuses(env):
    env(user=3, daily=0)
    assert quota.check(used_by_user=0, used_today=0).allowed
    assert quota.check(used_by_user=2, used_today=0).allowed
    verdict = quota.check(used_by_user=3, used_today=0)
    assert not verdict.allowed
    assert "3" in verdict.reason


def test_remaining_counts_down(env):
    env(user=3, daily=0)
    assert quota.check(0, 0).remaining == 3
    assert quota.check(2, 0).remaining == 1
    assert quota.check(3, 0).remaining == 0


def test_zero_means_unlimited(env):
    """The documented escape hatch for running a live demo."""
    env(user=0, daily=0)
    verdict = quota.check(used_by_user=9999, used_today=9999)
    assert verdict.allowed
    assert verdict.remaining == -1


def test_daily_cap_stops_everyone_including_a_fresh_account(env):
    """The per-account limit is only as strong as the cost of a new account. The daily cap
    is what makes the worst case a number we chose."""
    env(user=3, daily=10)
    verdict = quota.check(used_by_user=0, used_today=10)
    assert not verdict.allowed
    assert "today" in verdict.reason


def test_daily_cap_is_reported_before_the_personal_one(env):
    """Telling someone they have 2 left and then refusing them would be a worse answer
    than the true one."""
    env(user=3, daily=10)
    verdict = quota.check(used_by_user=3, used_today=10)
    assert "today" in verdict.reason


def test_a_broken_limit_falls_back_to_the_default(monkeypatch):
    """A typo in .env must not silently mean unlimited."""
    monkeypatch.setenv("FREE_RUN_LIMIT", "three")
    assert quota.user_limit() == quota.DEFAULT_USER_LIMIT
    monkeypatch.setenv("FREE_RUN_LIMIT", "-5")
    assert quota.user_limit() == 0  # clamped, and 0 is the explicit "no limit" value


# --- the ledger it counts -----------------------------------------------------------------


async def _db():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def test_deleting_a_diagram_does_not_refund_its_runs():
    """The obvious way to defeat a per-account quota: the runs lived on the session, so
    deleting the session deleted the evidence. They are kept and orphaned instead."""

    async def go():
        engine, sm = await _db()
        async with sm() as db:
            user = await repo.create_user(db, "a@example.com", "hash")
            session = await repo.create_session(db, user_id=user.id)
            for _ in range(3):
                await repo.record_run(db, user_id=user.id, session_id=session.id, input_kind="text")
            assert await repo.count_runs_for_user(db, user.id) == 3

            assert await repo.delete_session(db, session.id, user.id)
            assert await repo.count_runs_for_user(db, user.id) == 3
        await engine.dispose()

    asyncio.run(go())


def test_runs_are_counted_per_user_not_globally():
    async def go():
        engine, sm = await _db()
        async with sm() as db:
            one = await repo.create_user(db, "one@example.com", "hash")
            two = await repo.create_user(db, "two@example.com", "hash")
            await repo.record_run(db, user_id=one.id, session_id=None, input_kind="text")
            await repo.record_run(db, user_id=one.id, session_id=None, input_kind="text")
            await repo.record_run(db, user_id=two.id, session_id=None, input_kind="text")

            assert await repo.count_runs_for_user(db, one.id) == 2
            assert await repo.count_runs_for_user(db, two.id) == 1
        await engine.dispose()

    asyncio.run(go())


def test_daily_count_ignores_yesterday():
    async def go():
        engine, sm = await _db()
        async with sm() as db:
            user = await repo.create_user(db, "a@example.com", "hash")
            old = await repo.record_run(db, user_id=user.id, session_id=None, input_kind="text")
            old.created_at = datetime.now(UTC) - timedelta(days=2)
            await db.commit()
            await repo.record_run(db, user_id=user.id, session_id=None, input_kind="text")

            midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            assert await repo.count_runs_since(db, midnight) == 1
            # The personal allowance is lifetime, not daily — yesterday still counts.
            assert await repo.count_runs_for_user(db, user.id) == 2
        await engine.dispose()

    asyncio.run(go())


def test_reset_clears_one_account_only():
    async def go():
        engine, sm = await _db()
        async with sm() as db:
            one = await repo.create_user(db, "one@example.com", "hash")
            two = await repo.create_user(db, "two@example.com", "hash")
            await repo.record_run(db, user_id=one.id, session_id=None, input_kind="text")
            await repo.record_run(db, user_id=two.id, session_id=None, input_kind="text")

            assert await repo.reset_runs_for_user(db, one.id) == 1
            assert await repo.count_runs_for_user(db, one.id) == 0
            assert await repo.count_runs_for_user(db, two.id) == 1
        await engine.dispose()

    asyncio.run(go())


# --- the endpoint that spends the money ---------------------------------------------------


@pytest.fixture
def client(monkeypatch, tmp_path):
    """A signed-up client against a database of its own.

    A file rather than `:memory:`. The in-memory form needs StaticPool to keep one shared
    connection alive, and that connection gets created on a throwaway event loop — which
    holds up on its own but not after a dozen other modules have each made one. The
    symptom is a table that exists refusing to be found, several modules later, only in a
    full run. A file has none of that: any connection on any loop sees the same database.
    """
    from fastapi.testclient import TestClient

    from app.auth import throttle
    from app.db.engine import get_db
    from app.main import app

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'quota.db'}")
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db():
        async with sm() as db:
            yield db

    async def create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_tables())
    monkeypatch.setenv("COOKIE_SECURE", "false")
    app.dependency_overrides[get_db] = override_db
    throttle.reset_for_tests()
    with TestClient(app) as c:
        signed = c.post(
            "/auth/signup",
            json={"email": "demo@example.com", "password": "correct horse battery"},
        )
        assert signed.status_code == 201, signed.text
        yield c
    app.dependency_overrides.clear()


def test_stream_refuses_once_the_allowance_is_spent(client, env, monkeypatch):
    """The whole point: the refusal happens before anything reaches a model.

    The graph is replaced with something that fails loudly, so a test that accidentally
    got past the gate would error rather than quietly bill someone.
    """
    env(user=2, daily=0)

    called = []

    def explode(*_args, **_kwargs):
        called.append(1)
        raise AssertionError("the graph ran after the quota was spent")

    monkeypatch.setattr("app.main.graph.astream", explode, raising=False)

    body = {"message": "", "payload": "draw a system", "session_id": "s1"}
    # Two allowed runs. They reach the graph — which explodes — but the run is already
    # recorded by then, which is the behaviour under test: spending is what counts.
    for _ in range(2):
        try:
            client.post("/agent/stream", json=body)
        except AssertionError:
            pass

    third = client.post("/agent/stream", json=body)
    assert third.status_code == 429
    assert "2 diagram generations" in third.json()["detail"]
    assert third.headers.get("X-Canvo-Quota") == "2/2"
    assert len(called) == 2, "the third request must not have reached the graph"


def test_me_reports_the_allowance(client, env):
    env(user=3, daily=0)
    me = client.get("/auth/me").json()
    assert me["runs_used"] == 0
    assert me["runs_limit"] == 3


def test_quota_is_per_account(client, env):
    """A second account starts fresh — which is exactly why the daily cap exists."""
    env(user=1, daily=0)
    client.post("/auth/logout")
    client.post(
        "/auth/signup", json={"email": "other@example.com", "password": "correct horse battery"}
    )
    assert client.get("/auth/me").json()["runs_used"] == 0


def test_login_reports_the_real_count_not_zero(client, env, monkeypatch):
    """The bug this exists for: `_account` defaulted `runs_used` to 0, so signing back in
    told the client it had a full allowance. It showed "3 left", the user wrote a prompt,
    and the server refused — the UI had lied about a limit it was displaying."""
    env(user=3, daily=0)
    import app.main

    # Two runs, reaching a graph that does nothing.
    async def nothing(*_a, **_k):
        return
        yield  # pragma: no cover - makes this an async generator

    # Through monkeypatch, not a bare assignment: `graph` is a module-level singleton, so
    # setting the attribute directly would leave every test that ran afterwards driving a
    # graph that does nothing. It did, and two of them failed.
    monkeypatch.setattr(app.main.graph, "astream", nothing)
    body = {"message": "", "payload": "draw a system", "session_id": "s1"}
    for _ in range(2):
        client.post("/agent/stream", json=body)

    assert client.get("/auth/me").json()["runs_used"] == 2

    # Sign out and back in — the count must survive the round trip.
    client.post("/auth/logout")
    again = client.post(
        "/auth/login", json={"email": "demo@example.com", "password": "correct horse battery"}
    )
    assert again.status_code == 200
    assert again.json()["runs_used"] == 2, "logging in must not appear to refund the allowance"
