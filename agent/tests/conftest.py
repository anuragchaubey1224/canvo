"""Keep the suite offline, unbilled, and away from the developer's data.

`app.main` calls `load_dotenv()` at import time. Any test module that imports it therefore
puts the developer's real provider key into the environment, and from that moment every
test exercising the freeform path stops hitting the deterministic stub and starts making
live, billed requests. It is silent: the tests still pass or fail for plausible-looking
reasons, and the only symptom is a smaller balance.

Clearing the variables isn't enough on its own — the next `import app.main` simply reads
the .env again. So we neuter `load_dotenv` itself. conftest is imported before any test
module, so by the time anything imports the app there is nothing left to load.

Any test that genuinely needs a model must stub the client. It must never reach for a key.

The same argument applies to the database. `DATABASE_URL` is unset in a normal shell, so
`app.db.engine` falls back to `./canvo.db` — the file holding the developer's own account
and diagrams. Every test that builds a TestClient runs the app's lifespan, which migrates
that file, and any request whose dependency override does not take writes to it. Both
happened: a test run left two accounts and two ledger rows in a real database.

Overriding `get_db` per fixture is not enough, because it only covers what remembers to
use it. Pointing the whole suite at a throwaway file is: there is then no path, however
forgetful, from a test to the developer's data.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import dotenv

_PROVIDER_ENV = (
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_SPEC_MODEL",
    "LLM_PLAN_MODEL",
    "LLM_VISION_MODEL",
)


def _no_dotenv(*_args, **_kwargs) -> bool:
    """Stand-in for `dotenv.load_dotenv`. Returns False, as it does when there's no file."""
    return False


# Module scope on purpose: this has to happen before `app.main` is imported, which is
# during collection — earlier than any fixture can run.
dotenv.load_dotenv = _no_dotenv  # type: ignore[assignment]
for _name in _PROVIDER_ENV:
    os.environ.pop(_name, None)


# --- database ----------------------------------------------------------------------------

# Set before `app.db.engine` is imported, for the same reason as the dotenv patch above:
# the engine reads this at call time, but the lifespan can run during collection.
_TEST_DB = Path(tempfile.gettempdir()) / "canvo-tests.db"
_TEST_DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB}"
# The tests that want a database build their own in memory; nothing should be relying on
# the app migrating this one for them.
os.environ["RUN_MIGRATIONS"] = "false"
