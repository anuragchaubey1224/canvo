"""A guard, like tests/test_offline_guard.py.

That one exists because a test suite that silently starts spending money looks exactly
like one that doesn't. This one exists because a test suite that silently writes to the
developer's database looks exactly like one that doesn't — until an account you never
created shows up in it, which is how this was found.
"""

from __future__ import annotations

import os

from app.db.engine import _db_url


def test_the_suite_never_points_at_the_development_database():
    url = _db_url()
    assert "canvo-tests" in url, f"tests must use a throwaway database, got {url}"
    assert not url.endswith("/canvo.db"), "that is the developer's own database"


def test_app_startup_migrations_are_disabled_for_tests():
    """A TestClient context manager runs the app's lifespan. Left on, it migrates whatever
    DATABASE_URL points at, on every test module that builds a client."""
    assert os.getenv("RUN_MIGRATIONS") == "false"


def test_get_db_is_the_object_the_routes_actually_depend_on():
    """`app.dependency_overrides` is keyed by function identity.

    Reloading `app.db.engine` rebinds `get_db` to a new object while every route keeps the
    original in its `Depends(...)` default. Overrides registered against the new one then
    match nothing and quietly fall through to the real engine — which is how test accounts
    reached a developer's database. If this ever fails again, something reloaded the module.
    """
    from fastapi.routing import APIRoute

    from app.db.engine import get_db
    from app.main import app

    depended = {
        d.call
        for route in app.routes
        if isinstance(route, APIRoute)
        for d in route.dependant.dependencies
        if getattr(d.call, "__name__", "") == "get_db"
    }
    # Nested dependencies (current_user takes get_db too) are resolved recursively by
    # FastAPI; the top level is enough to catch a rebind.
    assert depended, "no route depends on get_db — has it been renamed?"
    assert depended == {get_db}, "a route depends on a different get_db object than tests import"
