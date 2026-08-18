"""Repository layer — all DB access goes through here (no ORM in routes)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuthSession, Message, Run, Session, User

# A provisional conversation title taken from the first prompt. The client replaces it
# with the spec's own title once the Spec Writer has one, so the name sharpens as the
# run progresses rather than staying "Untitled" until the user renames it by hand.
_TITLE_MAX = 60


async def create_session(
    db: AsyncSession, title: str = "Untitled", user_id: str | None = None
) -> Session:
    obj = Session(id=uuid.uuid4().hex, title=title, user_id=user_id)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get_session(
    db: AsyncSession, session_id: str, user_id: str | None = None
) -> Session | None:
    """Fetch a diagram. Passing `user_id` scopes it to that owner — every route that
    serves a diagram must pass one, or an id becomes a capability anyone can guess at."""
    obj = await db.get(Session, session_id)
    if obj is None:
        return None
    if user_id is not None and obj.user_id != user_id:
        return None
    return obj


async def save_snapshot(
    db: AsyncSession, session_id: str, snapshot: str, user_id: str | None = None
) -> Session | None:
    obj = await get_session(db, session_id, user_id)
    if obj is None:
        return None
    obj.snapshot = snapshot
    await db.commit()
    await db.refresh(obj)
    return obj


async def list_sessions(
    db: AsyncSession, user_id: str, limit: int = 50
) -> list[tuple[Session, int]]:
    """One owner's conversations, most recently touched first, with turn counts."""
    counts = (
        select(Message.session_id, func.count(Message.id).label("n"))
        .group_by(Message.session_id)
        .subquery()
    )
    rows = await db.execute(
        select(Session, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.session_id == Session.id)
        .where(Session.user_id == user_id)
        .order_by(Session.updated_at.desc())
        .limit(limit)
    )
    return [(session, int(n)) for session, n in rows.all()]


async def rename_session(
    db: AsyncSession, session_id: str, title: str, user_id: str | None = None
) -> Session | None:
    obj = await get_session(db, session_id, user_id)
    if obj is None:
        return None
    obj.title = title.strip()[:_TITLE_MAX] or "Untitled"
    await db.commit()
    await db.refresh(obj)
    return obj


async def delete_session(db: AsyncSession, session_id: str, user_id: str | None = None) -> bool:
    obj = await get_session(db, session_id, user_id)
    if obj is None:
        return False
    await db.execute(delete(Message).where(Message.session_id == session_id))
    await db.execute(delete(Run).where(Run.session_id == session_id))
    await db.delete(obj)
    await db.commit()
    return True


async def add_message(
    db: AsyncSession,
    session_id: str,
    role: str,
    text: str,
    activity: str | None = None,
    user_id: str | None = None,
) -> Message | None:
    session = await get_session(db, session_id, user_id)
    if session is None:
        return None
    msg = Message(session_id=session_id, role=role, text=text, activity=activity)
    db.add(msg)
    # Keep the conversation at the top of the history list, and give an unnamed one a
    # working title from the first thing the user actually asked for.
    session.updated_at = datetime.now(UTC)
    if role == "user" and session.title in ("", "Untitled") and text.strip():
        session.title = " ".join(text.split())[:_TITLE_MAX]
    await db.commit()
    await db.refresh(msg)
    return msg


async def list_messages(
    db: AsyncSession, session_id: str, user_id: str | None = None
) -> list[Message]:
    if await get_session(db, session_id, user_id) is None:
        return []
    rows = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.id)
    )
    return list(rows.scalars().all())


async def record_run(
    db: AsyncSession, session_id: str, input_kind: str, shape_count: int, iterations: int
) -> Run:
    run = Run(
        session_id=session_id,
        input_kind=input_kind,
        shape_count=shape_count,
        iterations=iterations,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


# --------------------------------------------------------------------------------------
# Accounts and logged-in browsers
# --------------------------------------------------------------------------------------

SESSION_TTL = timedelta(days=30)
# Even an actively used session eventually has to be re-established, so a token that
# quietly leaked can't live forever behind a sliding window.
SESSION_MAX_AGE = timedelta(days=90)


def normalise_email(email: str) -> str:
    """Lower-cased and stripped. Stored this way so the UNIQUE index *is* the
    case-insensitivity guarantee, rather than every call site remembering to fold."""
    return email.strip().lower()


async def create_user(db: AsyncSession, email: str, password_hash: str) -> User:
    user = User(id=uuid.uuid4().hex, email=normalise_email(email), password_hash=password_hash)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    rows = await db.execute(select(User).where(User.email == normalise_email(email)))
    return rows.scalar_one_or_none()


async def update_password_hash(db: AsyncSession, user_id: str, password_hash: str) -> None:
    user = await db.get(User, user_id)
    if user is None:
        return
    user.password_hash = password_hash
    await db.commit()


async def create_auth_session(db: AsyncSession, user_id: str, token_hash: str) -> AuthSession:
    now = datetime.now(UTC)
    row = AuthSession(
        token_hash=token_hash,
        user_id=user_id,
        created_at=now,
        last_seen_at=now,
        expires_at=now + SESSION_TTL,
    )
    db.add(row)
    await db.commit()
    return row


async def resolve_auth_session(db: AsyncSession, token_hash: str) -> User | None:
    """The user behind a session token, or None if there isn't a live one.

    Expiry slides forward on use so an active tab is never logged out mid-thought, but
    only up to `SESSION_MAX_AGE` from when the session began.
    """
    row = await db.get(AuthSession, token_hash)
    if row is None:
        return None

    now = datetime.now(UTC)
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC)
    if expires <= now or created + SESSION_MAX_AGE <= now:
        await db.delete(row)
        await db.commit()
        return None

    # Only write when it actually moves; otherwise every request is a database write.
    if now - (
        row.last_seen_at.replace(tzinfo=UTC) if not row.last_seen_at.tzinfo else row.last_seen_at
    ) > timedelta(hours=1):
        row.last_seen_at = now
        row.expires_at = min(now + SESSION_TTL, created + SESSION_MAX_AGE)
        await db.commit()

    return await db.get(User, row.user_id)


async def delete_auth_session(db: AsyncSession, token_hash: str) -> None:
    await db.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash))
    await db.commit()


async def delete_all_auth_sessions(db: AsyncSession, user_id: str) -> None:
    """Sign out everywhere — used on logout-all and after a password change."""
    await db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
    await db.commit()


async def adopt_orphan_sessions(db: AsyncSession, user_id: str) -> int:
    """Hand diagrams made before accounts existed to the first account created.

    Without this, upgrading a local install silently hides everything the developer
    already drew. It only ever fires for the very first user — see the caller.
    """
    rows = await db.execute(select(Session).where(Session.user_id.is_(None)))
    orphans = list(rows.scalars().all())
    for row in orphans:
        row.user_id = user_id
    if orphans:
        await db.commit()
    return len(orphans)


async def count_users(db: AsyncSession) -> int:
    rows = await db.execute(select(func.count(User.id)))
    return int(rows.scalar_one())
