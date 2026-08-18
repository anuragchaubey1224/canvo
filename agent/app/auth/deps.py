"""Who is making this request.

`current_user` is the only way a route learns the caller's identity, and every route that
touches a diagram takes it. That is the point: identity is a *parameter*, so a route that
forgets to ask for it also can't accidentally read someone else's data — it has no user id
to filter by and won't compile past review.
"""

from __future__ import annotations

import os

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import COOKIE_NAME, hash_token
from app.db import repo
from app.db.engine import get_db
from app.db.models import User


def cookie_secure() -> bool:
    """Secure cookies everywhere except plain-http local development.

    Defaults to ON: the failure mode of forgetting to set it in production (a session
    token sent in the clear) is far worse than the failure mode of setting it in dev
    (the cookie is simply ignored, and you notice immediately).
    """
    return os.getenv("COOKIE_SECURE", "true").strip().lower() not in ("0", "false", "no")


def set_session_cookie(response: Response, token: str, max_age_seconds: int) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=max_age_seconds,
        httponly=True,  # unreadable from JavaScript, so an XSS can't exfiltrate it
        secure=cookie_secure(),
        # Lax, not None: the browser then refuses to attach this cookie to a cross-site
        # request, which is CSRF protection we get without a token to manage. It requires
        # the API to be same-site with the app (api.canvo.app, not a different domain).
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=cookie_secure())


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """The signed-in user, or 401."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="not signed in")
    user = await repo.resolve_auth_session(db, hash_token(token))
    if user is None:
        raise HTTPException(status_code=401, detail="session expired")
    return user


async def optional_user(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
    """Same, but returns None instead of raising — for routes that may serve anonymously."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return await repo.resolve_auth_session(db, hash_token(token))


def client_ip(request: Request) -> str:
    """Best-effort client address for throttling.

    `X-Forwarded-For` is only trustworthy behind a proxy that overwrites it; we read the
    first hop when present because that is how Render and Cloudflare pass it, and fall
    back to the socket. It is a throttling key, not an authorisation input.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
