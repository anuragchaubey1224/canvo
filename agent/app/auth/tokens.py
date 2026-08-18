"""Session tokens.

Sessions are **opaque random strings**, not JWTs. That is a deliberate choice for a
first-party web app:

  - Revocation is a DELETE. A JWT is valid until it expires no matter what the server
    thinks, so "log out everywhere", "this device was stolen" and "ban this account" all
    need a server-side blocklist — at which point you have the database lookup you were
    trying to avoid, plus a signing key to rotate and a family of `alg` confusion bugs.
  - There is nothing to parse, so there is nothing to parse wrong.

The token is 256 bits from `secrets`, and only its SHA-256 lands in the database. A leaked
database therefore hands the attacker no usable session — the same reason we hash
passwords, except a fast hash is correct here: the input is already full-entropy random,
so there is no dictionary to run against it.
"""

from __future__ import annotations

import hashlib
import secrets

# 32 bytes → 256 bits of entropy. Guessing is not a threat model at this size.
_TOKEN_BYTES = 32

COOKIE_NAME = "canvo_session"


def new_token() -> tuple[str, str]:
    """A fresh session token: (secret to send to the client, hash to store)."""
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
