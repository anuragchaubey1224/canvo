"""Async engine + session factory. SQLite for dev, Postgres via DATABASE_URL for prod."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models import Base

logger = logging.getLogger(__name__)

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
    """Bring the database up to the current schema.

    Alembic is the only thing that changes the schema now — `create_all` was fine while
    there was nothing to preserve, but it silently ignores tables that already exist, so a
    new column on an existing install just never appeared.

    Running migrations on startup suits a single instance, which is what we deploy. With
    several, run `alembic upgrade head` as a release step instead and set
    RUN_MIGRATIONS=false, or two booting workers will race for the same lock.
    """
    if os.getenv("RUN_MIGRATIONS", "true").strip().lower() in ("0", "false", "no"):
        return
    async with engine().begin() as conn:
        await conn.run_sync(_upgrade_to_head)


def _alembic_config():
    from alembic.config import Config

    root = Path(__file__).resolve().parents[2]  # agent/
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return config


def _upgrade_to_head(conn) -> None:
    """Migrate, adopting a database that predates Alembic rather than failing on it.

    A local install created by the old `create_all` already has every table but no
    `alembic_version` row, so `upgrade head` would try to CREATE TABLE and abort. Stamping
    it records "you are already at this revision" without touching the data — the standard
    way to bring an existing database under migration control, and the difference between
    a developer keeping their diagrams and losing them.
    """
    from alembic.migration import MigrationContext
    from alembic.runtime.environment import EnvironmentContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import inspect

    config = _alembic_config()
    scripts = ScriptDirectory.from_config(config)
    head = scripts.get_current_head()
    if head is None:
        return  # no migrations exist yet

    already_versioned = MigrationContext.configure(conn).get_current_revision() is not None
    predates_alembic = "users" in set(inspect(conn).get_table_names())

    def run(rev, _context):
        if not already_versioned and predates_alembic:
            # Record the revision WITHOUT running it. Returning an empty list here would
            # run nothing *and* write nothing, leaving the database permanently unversioned
            # — the next migration would then try to create tables that already exist.
            return scripts._stamp_revs(head, rev)
        return scripts._upgrade_revs(head, rev)

    with EnvironmentContext(
        config,
        scripts,
        fn=run,
        destination_rev=head,
        starting_rev=None,
        as_sql=False,
    ) as env:
        env.configure(connection=conn, target_metadata=Base.metadata, render_as_batch=True)
        with env.begin_transaction():
            env.run_migrations()

    if not already_versioned and predates_alembic:
        logger.warning("database predates Alembic — stamped at %s, no tables touched", head)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yields a request-scoped session."""
    async with session_factory()() as db:
        yield db
