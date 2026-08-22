"""How much of the model this deployment is willing to buy.

Two limits, because they stop different things:

  - **per account** — one person cannot sit there generating all afternoon. This is the
    demo allowance, and it is what the UI counts down.
  - **per day, across everyone** — the backstop. A per-account limit is only as good as
    the cost of a new account, and a new account costs an attacker one disposable inbox.
    A global cap means the worst case is a number you chose, not a number they chose.

Both are read from the environment at call time rather than import time, so changing
`.env` and restarting is enough — no code edit to run a live demo with the limit lifted.

Enforcement happens in `/agent/stream` before any model call. Doing it in the client
would be a suggestion: the endpoint is public to anyone with a session cookie.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# A number that lets someone see the product work end to end, more than once, and stop.
DEFAULT_USER_LIMIT = 3
# Roughly a few dollars a day at the current model. Chosen to be survivable, not generous.
DEFAULT_DAILY_LIMIT = 60


def _limit(name: str, default: int) -> int:
    """A limit from the environment. `0` disables it — that is the documented escape
    hatch for running a demo, not an accident."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(0, value)


def user_limit() -> int:
    return _limit("FREE_RUN_LIMIT", DEFAULT_USER_LIMIT)


def daily_limit() -> int:
    return _limit("DAILY_RUN_LIMIT", DEFAULT_DAILY_LIMIT)


@dataclass(frozen=True)
class Verdict:
    """Whether this run may proceed, and what to tell the person if not."""

    allowed: bool
    used: int
    limit: int
    reason: str = ""

    @property
    def remaining(self) -> int:
        # An unlimited deployment has no meaningful remainder; -1 says so without the
        # caller having to special-case `limit == 0` everywhere.
        return -1 if self.limit == 0 else max(0, self.limit - self.used)


_USER_EXHAUSTED = (
    "You've used all {limit} diagram generations on this account. "
    "This is a demo deployment with a fixed allowance."
)
_DAILY_EXHAUSTED = (
    "Canvo has hit its generation limit for today. This is a demo deployment with a "
    "daily cap — try again tomorrow."
)


def check(used_by_user: int, used_today: int) -> Verdict:
    """Decide before spending anything. `used_*` are counts of runs already started."""
    per_user = user_limit()
    per_day = daily_limit()

    # The global cap is checked first: when it is hit, nobody gets a run, and telling a
    # user "you have 2 left" and then refusing them would be a worse answer than the
    # true one.
    if per_day and used_today >= per_day:
        return Verdict(False, used_by_user, per_user, _DAILY_EXHAUSTED)
    if per_user and used_by_user >= per_user:
        return Verdict(False, used_by_user, per_user, _USER_EXHAUSTED.format(limit=per_user))
    return Verdict(True, used_by_user, per_user)
