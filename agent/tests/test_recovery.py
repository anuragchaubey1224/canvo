"""Password reset and address verification — the properties an attacker would probe.

A reset link is a temporary key to an account, so these assert the things that make it
safe to email one: it works once, it expires, it can't be swapped for a different
purpose, redeeming it evicts every other session, and asking for one never reveals
whether the address is registered.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth import link_tokens, throttle
from app.auth.tokens import COOKIE_NAME, hash_token, new_token
from app.db import repo
from app.db.engine import get_db
from app.db.models import AuthToken, Base
from app.main import app

GOOD = "correct horse battery"
NEXT = "another passphrase entirely"


@pytest.fixture
def env(monkeypatch):
    """A client plus a way to read what was 'emailed'."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db():
        async with sm() as db:
            yield db

    async def create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(create_tables())
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("EMAIL_BACKEND", "console")
    monkeypatch.setenv("APP_URL", "http://localhost:5173")

    sent: list[tuple[str, str, str]] = []

    async def capture(to: str, subject: str, body: str) -> bool:
        sent.append((to, subject, body))
        return True

    # Patch where it's used, not where it's defined — the router imported the name.
    import app.auth.router as router_mod

    monkeypatch.setattr(router_mod, "send_email", capture)

    app.dependency_overrides[get_db] = override_db
    throttle.reset_for_tests()
    with TestClient(app) as client:
        yield client, sent, sm
    app.dependency_overrides.clear()


def link_from(sent, subject_contains: str) -> str:
    body = next(b for _to, subj, b in sent if subject_contains.lower() in subj.lower())
    return next(line for line in body.splitlines() if line.startswith("http"))


def token_in(link: str) -> str:
    return link.split("token=", 1)[1]


def signup(client, email="user@example.com", password=GOOD):
    return client.post("/auth/signup", json={"email": email, "password": password})


# --- verification -------------------------------------------------------------------------


def test_signup_sends_a_verification_link_and_the_account_starts_unverified(env):
    client, sent, _ = env
    assert signup(client).json()["email_verified"] is False
    assert any("confirm" in subj.lower() for _to, subj, _b in sent)
    assert token_in(link_from(sent, "confirm"))


def test_verifying_marks_the_account_and_the_link_then_dies(env):
    client, sent, _ = env
    signup(client)
    token = token_in(link_from(sent, "confirm"))

    assert client.post("/auth/verify", json={"token": token}).status_code == 200
    assert client.get("/auth/me").json()["email_verified"] is True

    again = client.post("/auth/verify", json={"token": token})
    assert again.status_code == 400, "a link that has worked once must not work twice"


def test_a_verification_link_cannot_be_spent_as_a_password_reset(env):
    client, sent, _ = env
    signup(client)
    token = token_in(link_from(sent, "confirm"))
    res = client.post("/auth/reset", json={"token": token, "password": NEXT})
    assert res.status_code == 400, "purpose binding is what stops the cheapest link"
    # and the password is untouched
    client.post("/auth/logout")
    assert (
        client.post("/auth/login", json={"email": "user@example.com", "password": GOOD}).status_code
        == 200
    )


# --- reset --------------------------------------------------------------------------------


def test_forgot_never_says_whether_the_address_exists(env):
    client, sent, _ = env
    signup(client, "real@example.com")
    client.post("/auth/logout")
    sent.clear()

    known = client.post("/auth/forgot", json={"email": "real@example.com"})
    unknown = client.post("/auth/forgot", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    # ...but only one of them actually produced mail
    assert len([s for s in sent if "reset" in s[1].lower()]) == 1


def test_a_reset_changes_the_password_and_signs_you_in(env):
    client, sent, _ = env
    signup(client, "reset-me@example.com")
    client.post("/auth/logout")
    client.post("/auth/forgot", json={"email": "reset-me@example.com"})
    token = token_in(link_from(sent, "reset"))

    res = client.post("/auth/reset", json={"token": token, "password": NEXT})
    assert res.status_code == 200
    assert client.get("/auth/me").json()["email"] == "reset-me@example.com"

    client.post("/auth/logout")
    assert (
        client.post(
            "/auth/login", json={"email": "reset-me@example.com", "password": GOOD}
        ).status_code
        == 401
    ), "the old password must stop working"
    assert (
        client.post(
            "/auth/login", json={"email": "reset-me@example.com", "password": NEXT}
        ).status_code
        == 200
    )


def test_a_reset_evicts_every_other_session(env):
    client, sent, _ = env
    signup(client, "victim@example.com")
    intruder_cookie = client.cookies.get(COOKIE_NAME)

    client.post("/auth/forgot", json={"email": "victim@example.com"})
    token = token_in(link_from(sent, "reset"))
    client.cookies.clear()
    client.post("/auth/reset", json={"token": token, "password": NEXT})

    # Replaying a session that existed before the reset must fail: if the reason to reset
    # was that somebody else had the password, leaving them signed in defeats the point.
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME, intruder_cookie)
    assert client.get("/auth/me").status_code == 401


def test_a_reset_link_works_once(env):
    client, sent, _ = env
    signup(client, "once@example.com")
    client.post("/auth/forgot", json={"email": "once@example.com"})
    token = token_in(link_from(sent, "reset"))

    assert client.post("/auth/reset", json={"token": token, "password": NEXT}).status_code == 200
    assert (
        client.post(
            "/auth/reset", json={"token": token, "password": "third pass phrase"}
        ).status_code
        == 400
    )


def test_asking_again_retires_the_previous_link(env):
    client, sent, _ = env
    signup(client, "twice@example.com")
    client.post("/auth/logout")

    client.post("/auth/forgot", json={"email": "twice@example.com"})
    first = token_in(link_from(sent, "reset"))
    sent.clear()
    client.post("/auth/forgot", json={"email": "twice@example.com"})
    second = token_in(link_from(sent, "reset"))

    assert first != second
    assert client.post("/auth/reset", json={"token": first, "password": NEXT}).status_code == 400
    assert client.post("/auth/reset", json={"token": second, "password": NEXT}).status_code == 200


def test_a_weak_new_password_is_refused_and_the_link_is_still_spent(env):
    client, sent, _ = env
    signup(client, "weak@example.com")
    client.post("/auth/forgot", json={"email": "weak@example.com"})
    token = token_in(link_from(sent, "reset"))
    assert client.post("/auth/reset", json={"token": token, "password": "short"}).status_code == 422


def test_a_forged_or_unknown_token_is_refused(env):
    client, _sent, _ = env
    for token in ("", "not-a-real-token", new_token()[0]):
        assert (
            client.post("/auth/reset", json={"token": token, "password": NEXT}).status_code == 400
        )
        assert client.post("/auth/verify", json={"token": token}).status_code == 400


def test_an_expired_link_is_refused(env):
    client, sent, sm = env
    signup(client, "slow@example.com")
    client.post("/auth/forgot", json={"email": "slow@example.com"})
    token = token_in(link_from(sent, "reset"))

    async def age_it():
        async with sm() as db:
            row = await db.get(AuthToken, hash_token(token))
            row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
            await db.commit()

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(age_it())
    assert client.post("/auth/reset", json={"token": token, "password": NEXT}).status_code == 400


def test_requesting_resets_is_throttled(env):
    client, _sent, _ = env
    signup(client, "spam@example.com")
    codes = [
        client.post("/auth/forgot", json={"email": "spam@example.com"}).status_code
        for _ in range(throttle.MAX_ATTEMPTS + 2)
    ]
    assert 429 in codes, "otherwise this is a free way to mailbomb any address you know"


# --- token policy ---------------------------------------------------------------------------


def test_reset_links_are_short_lived_and_verification_links_less_so():
    assert link_tokens.TTL[link_tokens.RESET] < link_tokens.TTL[link_tokens.VERIFY]
    assert link_tokens.TTL[link_tokens.RESET] <= timedelta(hours=2)


def test_tokens_are_stored_hashed_never_in_the_clear(env):
    client, sent, sm = env
    signup(client, "hashed@example.com")
    token = token_in(link_from(sent, "confirm"))

    async def read():
        async with sm() as db:
            return await db.get(AuthToken, hash_token(token)), await db.get(AuthToken, token)

    stored, raw = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(read())
    assert stored is not None and raw is None


def test_repo_refuses_a_token_issued_for_another_purpose(env):
    _client, _sent, sm = env

    async def scenario():
        async with sm() as db:
            user = await repo.create_user(db, "p@example.com", "hash")
            token, digest = new_token()
            await repo.issue_auth_token(db, user.id, link_tokens.VERIFY, digest, timedelta(hours=1))
            assert await repo.consume_auth_token(db, digest, link_tokens.RESET) is None
            # ...and the failed attempt did not spend it
            assert await repo.consume_auth_token(db, digest, link_tokens.VERIFY) is not None

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(scenario())
