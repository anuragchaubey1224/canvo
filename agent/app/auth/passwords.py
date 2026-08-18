"""Password hashing and policy.

**Argon2id**, at OWASP's recommended floor (19 MiB, 2 iterations, 1 lane). It is the
memory-hard winner of the Password Hashing Competition: unlike bcrypt or PBKDF2, an
attacker with GPUs or ASICs gains far less, because the cost is RAM rather than clock.

Two rules the rest of the service depends on:

  - `verify` re-hashes transparently when the parameters change, so raising the cost later
    upgrades users as they log in instead of stranding old hashes.
  - `verify_dummy` burns the same work when no such account exists. Without it, a
    non-existent email answers measurably faster than a wrong password, which turns the
    login form into an account-enumeration oracle.

Policy follows NIST SP 800-63B: length is what matters, composition rules are not. Long
passphrases are encouraged and no rotation is forced.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

# OWASP Password Storage Cheat Sheet, Argon2id: m=19456 KiB, t=2, p=1.
_hasher = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)

MIN_LENGTH = 10
# Argon2 hashes the whole input, so an unbounded password is an unbounded amount of work
# for one unauthenticated request. 128 characters is far past any real passphrase.
MAX_LENGTH = 128

# Verified against on a missing account so the timing matches a real check.
_DUMMY_HASH = _hasher.hash("timing-equalisation-placeholder")


class PasswordRejected(ValueError):
    """The password doesn't meet policy. The message is safe to show the user."""


def check_policy(password: str, *, email: str = "") -> None:
    """Raise `PasswordRejected` if the password is unacceptable."""
    if len(password) < MIN_LENGTH:
        raise PasswordRejected(f"Use at least {MIN_LENGTH} characters.")
    if len(password) > MAX_LENGTH:
        raise PasswordRejected(f"Use at most {MAX_LENGTH} characters.")
    if password.strip() == "":
        raise PasswordRejected("Use at least one non-space character.")
    # Only worth checking for a local part long enough to be a real name. "a@…" would
    # otherwise reject virtually every password, since "a" appears in most of them.
    local = email.split("@")[0].strip().lower()
    if len(local) >= 4 and local in password.lower():
        raise PasswordRejected("Don't use your email address in your password.")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> tuple[bool, str | None]:
    """Check a password. Returns (ok, new_hash) — `new_hash` is set when the stored hash
    used weaker parameters than we use now and should be replaced."""
    try:
        _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False, None
    except Exception:
        # A corrupt or truncated hash must fail closed, never authenticate.
        return False, None
    return True, (_hasher.hash(password) if _hasher.check_needs_rehash(stored_hash) else None)


def verify_dummy(password: str) -> None:
    """Spend the same time as a real verification, for accounts that don't exist."""
    try:
        _hasher.verify(_DUMMY_HASH, password)
    except Exception:
        pass
