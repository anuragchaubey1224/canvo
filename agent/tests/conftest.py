"""Keep the suite offline — and unbilled.

`app.main` calls `load_dotenv()` at import time. Any test module that imports it therefore
puts the developer's real provider key into the environment, and from that moment every
test exercising the freeform path stops hitting the deterministic stub and starts making
live, billed requests. It is silent: the tests still pass or fail for plausible-looking
reasons, and the only symptom is a smaller balance.

Clearing the variables isn't enough on its own — the next `import app.main` simply reads
the .env again. So we neuter `load_dotenv` itself. conftest is imported before any test
module, so by the time anything imports the app there is nothing left to load.

Any test that genuinely needs a model must stub the client. It must never reach for a key.
"""

from __future__ import annotations

import os

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
