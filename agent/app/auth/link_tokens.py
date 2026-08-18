"""Single-use tokens for the links we email.

A password-reset link is a temporary key to an account, so it is held to stricter rules
than a session:

  - **Single use.** Consuming one marks it spent in the same transaction that reads it,
    so a link forwarded, logged by a mail scanner, or left in browser history is dead the
    moment it works once.
  - **Short lived.** An hour to reset, a day to verify. Long enough for a person who got
    distracted, short enough that an old inbox isn't a standing back door.
  - **Purpose-bound.** A verification token cannot be replayed as a reset token. Without
    this, the weakest link in the system sets the security of the strongest.
  - **Stored hashed**, exactly like sessions — a leaked database contains no usable links.

Issuing a new token of a purpose invalidates the account's earlier ones, so "send it
again" can't leave three live keys in three inboxes.
"""

from __future__ import annotations

from datetime import timedelta

RESET = "reset"
VERIFY = "verify"

# A reset link is a key to the account; a verification link only confirms an address, so
# it can afford to survive a night's sleep.
TTL = {RESET: timedelta(hours=1), VERIFY: timedelta(hours=24)}

SUBJECTS = {
    RESET: "Reset your Canvo password",
    VERIFY: "Confirm your email for Canvo",
}


def reset_body(link: str) -> str:
    return (
        "Someone asked to reset the password for this Canvo account.\n\n"
        f"{link}\n\n"
        "The link works once and expires in an hour. If it wasn't you, you can ignore "
        "this — nothing has changed, and your password still works."
    )


def verify_body(link: str) -> str:
    return (
        "Confirm this address so you can recover your Canvo account if you ever lose "
        "your password.\n\n"
        f"{link}\n\n"
        "The link works once and expires in a day."
    )


def body_for(purpose: str, link: str) -> str:
    return reset_body(link) if purpose == RESET else verify_body(link)
