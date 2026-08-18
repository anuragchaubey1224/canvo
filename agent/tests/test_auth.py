"""Auth — the properties that matter, exercised against a real in-memory database.

These are security tests, so they assert on behaviour an attacker would probe: whether
the API distinguishes a missing account from a wrong password, whether one user can read
another's diagrams, and whether the session cookie is safe to hand a browser.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth import throttle
from app.auth.passwords import (
    PasswordRejected,
    check_policy,
    hash_password,
    verify_password,
)
from app.auth.tokens import COOKIE_NAME, hash_token, new_token
from app.db.engine import get_db
from app.db.models import Base
from app.main import app

GOOD = "correct horse battery"


@pytest.fixture
def client(monkeypatch):
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

    import asyncio

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(create_tables())
    # The test client speaks http, and a browser (or httpx) will not send a Secure cookie
    # over http — the same reason local dev needs this. Production keeps the default.
    monkeypatch.setenv("COOKIE_SECURE", "false")
    app.dependency_overrides[get_db] = override_db
    throttle.reset_for_tests()
    # `lifespan` would run the real init_db against the developer's file; the tables are
    # already created above.
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def signup(client, email: str, password: str = GOOD):
    return client.post("/auth/signup", json={"email": email, "password": password})


# --- password handling -----------------------------------------------------------------


def test_hashes_are_salted_and_verify():
    a, b = hash_password(GOOD), hash_password(GOOD)
    assert a != b, "same password must not produce the same hash"
    assert a.startswith("$argon2id$")
    assert verify_password(a, GOOD)[0]
    assert not verify_password(a, GOOD + "x")[0]


def test_a_corrupt_hash_fails_closed():
    assert verify_password("not-a-hash", GOOD) == (False, None)
    assert verify_password("", GOOD) == (False, None)


def test_policy_rejects_short_and_email_derived_passwords():
    for bad in ("short", "         ", "x" * 200):
        with pytest.raises(PasswordRejected):
            check_policy(bad)
    with pytest.raises(PasswordRejected):
        check_policy("anurag12345", email="anurag@example.com")
    check_policy(GOOD, email="anurag@example.com")


def test_tokens_are_unique_and_stored_only_as_a_hash():
    token, digest = new_token()
    assert len(token) > 30 and token != digest
    assert hash_token(token) == digest
    assert new_token()[0] != new_token()[0]


# --- signup / login --------------------------------------------------------------------


def test_signup_signs_you_in_with_a_hardened_cookie(client):
    res = signup(client, "a@example.com")
    assert res.status_code == 201
    assert res.json()["email"] == "a@example.com"

    cookie = res.headers["set-cookie"]
    assert COOKIE_NAME in cookie
    assert "httponly" in cookie.lower(), "a readable cookie is stealable by any XSS"
    assert "samesite=lax" in cookie.lower(), "SameSite is the CSRF defence here"
    assert client.get("/auth/me").json()["email"] == "a@example.com"


def test_email_is_normalised_so_case_cannot_duplicate_an_account(client):
    signup(client, "Mixed@Example.COM")
    assert signup(client, "mixed@example.com").status_code == 409
    assert (
        client.post(
            "/auth/login", json={"email": "  MIXED@example.com ", "password": GOOD}
        ).status_code
        == 200
    )


def test_signup_does_not_confirm_that_an_address_exists(client):
    signup(client, "taken@example.com")
    client.post("/auth/logout")
    body = signup(client, "taken@example.com").json()["detail"]
    assert "taken" not in body.lower() and "exists" not in body.lower()


def test_login_answers_the_same_for_unknown_account_and_wrong_password(client):
    signup(client, "real@example.com")
    client.post("/auth/logout")

    unknown = client.post("/auth/login", json={"email": "ghost@example.com", "password": GOOD})
    wrong = client.post("/auth/login", json={"email": "real@example.com", "password": "nope-nope"})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


def test_weak_passwords_are_refused_at_signup(client):
    res = signup(client, "b@example.com", "short")
    assert res.status_code == 422
    assert (
        client.post("/auth/login", json={"email": "b@example.com", "password": "short"}).status_code
        == 401
    )


def test_repeated_failures_are_throttled(client):
    signup(client, "target@example.com")
    client.post("/auth/logout")
    codes = [
        client.post(
            "/auth/login", json={"email": "target@example.com", "password": "wrong-guess"}
        ).status_code
        for _ in range(throttle.MAX_ATTEMPTS + 2)
    ]
    assert 429 in codes, "a password form with no throttle is a password oracle"


# --- sessions --------------------------------------------------------------------------


def test_logout_kills_the_session_server_side(client):
    signup(client, "c@example.com")
    stolen = client.cookies.get(COOKIE_NAME)
    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401

    # Even replaying the exact cookie fails: the row is gone, not just the browser's copy.
    client.cookies.set(COOKIE_NAME, stolen)
    assert client.get("/auth/me").status_code == 401


def test_a_forged_cookie_is_rejected(client):
    client.cookies.set(COOKIE_NAME, "definitely-not-a-real-token")
    assert client.get("/auth/me").status_code == 401


# --- data isolation ----------------------------------------------------------------------


def test_diagrams_require_a_session(client):
    for call in (
        lambda: client.get("/sessions"),
        lambda: client.post("/sessions"),
        lambda: client.get("/sessions/anything/messages"),
        lambda: client.post("/agent/stream", json={"message": "hi"}),
    ):
        assert call().status_code == 401


def test_one_account_cannot_touch_anothers_diagram(client):
    signup(client, "owner@example.com")
    owned = client.post("/sessions").json()["id"]
    client.put(f"/sessions/{owned}/snapshot", json={"snapshot": '{"secret": 1}'})
    client.post("/auth/logout")

    signup(client, "intruder@example.com")
    assert client.get(f"/sessions/{owned}/snapshot").status_code == 404
    assert client.get(f"/sessions/{owned}/messages").json() == []
    assert client.delete(f"/sessions/{owned}").status_code == 404
    assert client.patch(f"/sessions/{owned}", json={"title": "mine now"}).status_code == 404
    assert [s["id"] for s in client.get("/sessions").json()] == []

    # And the owner still has it, untouched.
    client.post("/auth/logout")
    client.post("/auth/login", json={"email": "owner@example.com", "password": GOOD})
    assert client.get(f"/sessions/{owned}/snapshot").json()["snapshot"] == '{"secret": 1}'
