"""Migrations — that they build the schema the models describe, and adopt old databases.

The failure this exists for: someone adds a column to a model, `create_all` conjures it in
their local database and every test passes, and the migration that production actually
runs never gets written. Nothing catches it until a deploy. So the important test here
isn't "do the migrations run" — it's "after running them, does Alembic still see changes
it would want to generate?"
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.db.models import Base, User
from app.db.models import Session as DiagramSession

MODEL_TABLES = {"users", "auth_sessions", "auth_tokens", "sessions", "messages", "runs"}


def _upgrade(url: str) -> None:
    """Run migrations against a synchronous URL, the way init_db does asynchronously."""
    import app.db.engine as engine_mod

    sync = create_engine(url)
    with sync.begin() as conn:
        engine_mod._upgrade_to_head(conn)
    sync.dispose()


@pytest.fixture
def fresh_db(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'fresh.db'}"


def test_migrations_build_every_table_the_app_uses(fresh_db):
    _upgrade(fresh_db)
    with create_engine(fresh_db).connect() as conn:
        tables = set(inspect(conn).get_table_names())
    assert MODEL_TABLES <= tables
    assert "alembic_version" in tables


def test_the_models_and_the_migrations_have_not_drifted(fresh_db):
    """The one that earns its keep: a model change with no migration fails here."""
    _upgrade(fresh_db)
    sync = create_engine(fresh_db)
    with sync.connect() as conn:
        context = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(context, Base.metadata)
    sync.dispose()
    assert diff == [], (
        "the models describe a schema the migrations don't build — "
        "run `alembic revision --autogenerate` and commit the result"
    )


def test_running_migrations_twice_changes_nothing(fresh_db):
    _upgrade(fresh_db)
    _upgrade(fresh_db)  # a restart, a second worker, a re-deploy
    with create_engine(fresh_db).connect() as conn:
        assert MODEL_TABLES <= set(inspect(conn).get_table_names())


def test_a_database_from_before_alembic_is_stamped_not_rebuilt(tmp_path: Path):
    """An install created by the old `create_all` has the tables but no version row.
    Upgrading it must record the revision without touching a single row — the difference
    between a developer keeping their diagrams and losing them."""
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    legacy = create_engine(url)
    Base.metadata.create_all(legacy)  # exactly what init_db used to do
    # Written through the ORM: these columns have Python-side defaults, so raw SQL would
    # trip the NOT NULLs that the app itself never has to think about.
    with Session(legacy) as db:
        db.add(User(id="u1", email="old@example.com", password_hash="hash"))
        db.add(DiagramSession(id="s1", user_id="u1", title="Kept"))
        db.commit()
    legacy.dispose()

    _upgrade(url)

    check = create_engine(url)
    with check.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert conn.execute(text("SELECT title FROM sessions WHERE id='s1'")).scalar() == "Kept"
        assert (
            conn.execute(text("SELECT email FROM users WHERE id='u1'")).scalar()
            == "old@example.com"
        )
    check.dispose()


def test_init_db_can_be_switched_off_for_a_release_step(tmp_path, monkeypatch):
    """Several instances booting at once would race for the migration lock, so a
    multi-instance deploy runs migrations once as a release step instead.

    No reload. `init_db` reads RUN_MIGRATIONS and DATABASE_URL at call time, so the env is
    all this needs — and reloading the module was actively harmful: it rebinds `get_db` to
    a new function object while every route still holds the original in its `Depends(...)`
    default. Any later test that imported `get_db` fresh then registered its override
    against a key nothing matches, silently fell through to the real engine, and wrote to
    the developer's database. That is how two test accounts ended up in it.
    """
    import app.db.engine as engine_mod

    target = tmp_path / "untouched.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{target}")
    monkeypatch.setenv("RUN_MIGRATIONS", "false")
    # The engine is memoised per process, so a previous test's engine would be reused and
    # this one would never look at DATABASE_URL at all.
    monkeypatch.setattr(engine_mod, "_engine", None)
    asyncio.run(engine_mod.init_db())
    assert not target.exists()
    monkeypatch.setattr(engine_mod, "_engine", None)
