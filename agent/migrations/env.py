"""Alembic environment.

Two things worth knowing:

  - The URL comes from `DATABASE_URL`, never from alembic.ini. One source of truth means a
    migration cannot be pointed at the wrong database by an out-of-date config file.
  - The engine is async, because the app's is. `run_sync` bridges Alembic's synchronous
    migration API onto it rather than opening a second, differently-configured connection.

`render_as_batch` matters for SQLite: it has no real ALTER, so Alembic emulates one by
rebuilding the table. Without it, every future column drop or type change would work in
Postgres and fail on a developer's laptop.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./canvo.db")


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it — for reviewing what a deploy will do."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    config.set_main_option("sqlalchemy.url", database_url())
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
