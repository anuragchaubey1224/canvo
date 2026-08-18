"""Sign up, sign in, sign out.

Email and password for now, because it needs no third party to work and it is the base
every other method layers onto. Two things are built in from the start rather than
retrofitted, since both are much harder to add later:

  - **No account enumeration.** Signing up with a taken address, signing in with an
    unknown one, and signing in with a wrong password all answer the same way and take
    the same time. An endpoint that says "no such user" is a free list of your customers.
  - **Throttling on the login path**, keyed by account and by IP (see throttle.py).

Deliberately not here yet, and each is additive: email verification and password reset
(both need an SMTP provider), magic links, OAuth, and TOTP.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import throttle
from app.auth.deps import clear_session_cookie, client_ip, current_user, set_session_cookie
from app.auth.passwords import (
    PasswordRejected,
    check_policy,
    hash_password,
    verify_dummy,
    verify_password,
)
from app.auth.tokens import COOKIE_NAME, hash_token, new_token
from app.db import repo
from app.db.engine import get_db
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

# Deliberately loose. Real validation is "we sent mail to it and someone clicked"; a
# clever regex only rejects addresses that turn out to be valid.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")

# One message for every way a sign-in can fail, so the response never distinguishes
# "no such account" from "wrong password".
_BAD_CREDENTIALS = "Email or password is incorrect."


class Credentials(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)  # policy caps it lower; this stops absurd bodies


def _account(user: User) -> dict:
    return {"id": user.id, "email": user.email, "created_at": user.created_at.isoformat()}


def _ttl_seconds() -> int:
    return int(repo.SESSION_TTL.total_seconds())


async def _issue_session(db: AsyncSession, response: Response, user: User) -> None:
    token, token_hash = new_token()
    await repo.create_auth_session(db, user.id, token_hash)
    set_session_cookie(response, token, _ttl_seconds())


@router.post("/signup", status_code=201)
async def signup(
    body: Credentials,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    email = repo.normalise_email(body.email)
    if not _EMAIL.match(email):
        raise HTTPException(status_code=422, detail="That doesn't look like an email address.")
    try:
        check_policy(body.password, email=email)
    except PasswordRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Signup is a write, so it gets the same throttle as login — otherwise it is a free
    # way to make the server run Argon2 as fast as you can post.
    ip = client_ip(request)
    if not throttle.check(email, ip):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")

    if await repo.get_user_by_email(db, email) is not None:
        # Same shape and cost as success, so this doesn't reveal that the address exists.
        # The person who really owns it finds out by signing in or resetting.
        throttle.record_failure(email, ip)
        hash_password(body.password)
        raise HTTPException(
            status_code=409,
            detail="If that address is available you'll be signed in; otherwise sign in instead.",
        )

    first_user = await repo.count_users(db) == 0
    user = await repo.create_user(db, email, hash_password(body.password))
    if first_user:
        # A local install upgrading to accounts would otherwise hide every diagram the
        # developer already made. Only ever the first account, only ever ownerless rows.
        await repo.adopt_orphan_sessions(db, user.id)

    throttle.record_success(email, ip)
    await _issue_session(db, response, user)
    return _account(user)


@router.post("/login")
async def login(
    body: Credentials,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    email = repo.normalise_email(body.email)
    ip = client_ip(request)
    if not throttle.check(email, ip):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")

    user = await repo.get_user_by_email(db, email)
    if user is None:
        # Spend the same work as a real verification: without this, a missing account
        # answers in microseconds and the form becomes an account-existence oracle.
        verify_dummy(body.password)
        throttle.record_failure(email, ip)
        raise HTTPException(status_code=401, detail=_BAD_CREDENTIALS)

    ok, upgraded = verify_password(user.password_hash, body.password)
    if not ok:
        throttle.record_failure(email, ip)
        raise HTTPException(status_code=401, detail=_BAD_CREDENTIALS)
    if upgraded:
        # Argon2's cost was raised since this hash was written; re-store it now that we
        # have the plaintext, so the upgrade happens without asking anyone to do anything.
        await repo.update_password_hash(db, user.id, upgraded)

    throttle.record_success(email, ip)
    await _issue_session(db, response, user)
    return _account(user)


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Always succeeds — a logout that can fail leaves people stuck signed in."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        await repo.delete_auth_session(db, hash_token(token))
    clear_session_cookie(response)
    return {"ok": True}


@router.post("/logout-all")
async def logout_all(
    response: Response,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await repo.delete_all_auth_sessions(db, user.id)
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
async def me(user: User = Depends(current_user)):
    return _account(user)
