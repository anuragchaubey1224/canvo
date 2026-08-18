"""Login throttling.

A password form with no throttle is a password oracle: an attacker can try a common
password against every address they have, as fast as the network allows. Argon2 slows one
guess down; only a counter stops a million.

Two independent buckets, because they catch different attacks:

  - **per account** — someone hammering one inbox with a password list
  - **per client IP** — someone spraying one common password across many inboxes, which
    never trips a per-account limit

This implementation is in-process, which is honest for a single instance and wrong for
several: each worker would keep its own counts and the effective limit would multiply.
Moving it to Redis is a swap of `_Bucket` for a shared counter — the call sites don't
change. Until then, run one worker or accept the looser bound.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

# Deliberately generous for a person who forgot their password, hopeless for a script.
MAX_ATTEMPTS = 8
WINDOW_SECONDS = 15 * 60
# Keep the table from growing without bound on a long-running process.
_SWEEP_EVERY = 512


@dataclass
class _Bucket:
    hits: dict[str, list[float]] = field(default_factory=dict)
    since_sweep: int = 0

    def _sweep(self, now: float) -> None:
        cutoff = now - WINDOW_SECONDS
        for key in [k for k, v in self.hits.items() if not v or v[-1] < cutoff]:
            del self.hits[key]

    def blocked(self, key: str, now: float) -> bool:
        recent = [t for t in self.hits.get(key, ()) if t > now - WINDOW_SECONDS]
        self.hits[key] = recent
        return len(recent) >= MAX_ATTEMPTS

    def record(self, key: str, now: float) -> None:
        self.hits.setdefault(key, []).append(now)
        self.since_sweep += 1
        if self.since_sweep >= _SWEEP_EVERY:
            self.since_sweep = 0
            self._sweep(now)

    def clear(self, key: str) -> None:
        self.hits.pop(key, None)


_by_account = _Bucket()
_by_ip = _Bucket()


def check(email: str, ip: str) -> bool:
    """True when this attempt is allowed to proceed."""
    now = time.monotonic()
    return not (_by_account.blocked(email, now) or _by_ip.blocked(ip, now))


def record_failure(email: str, ip: str) -> None:
    now = time.monotonic()
    _by_account.record(email, now)
    _by_ip.record(ip, now)


def record_success(email: str, ip: str) -> None:
    """A correct password clears the account's count — a user who finally remembers it
    shouldn't stay locked out. The IP count stands: spraying succeeds on some address
    eventually, and that is exactly when we want to keep counting."""
    _by_account.clear(email)


def reset_for_tests() -> None:
    _by_account.hits.clear()
    _by_ip.hits.clear()
