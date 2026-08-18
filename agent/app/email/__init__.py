"""Outbound email.

One function, two backends. The default is `console`, which prints the message instead of
sending it — so a fresh clone has a working password-reset flow with no account anywhere,
and nobody has to stub a provider to develop against it. Set `EMAIL_BACKEND=resend` with a
key to actually deliver.

Sending is best-effort by design: a reset endpoint that 500s because the mail provider is
down tells an attacker the address exists (a missing account never calls the provider at
all) and tells a real user nothing useful. Failures are logged, and the caller still
answers the same way it always does.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def app_url() -> str:
    """Where the links in our emails point. The web app, not this service."""
    return os.getenv("APP_URL", "http://localhost:5173").rstrip("/")


async def send_email(to: str, subject: str, body: str) -> bool:
    """Deliver one plain-text message. Returns whether it went out; never raises."""
    backend = os.getenv("EMAIL_BACKEND", "console").strip().lower()
    try:
        if backend == "resend":
            from app.email.backends import send_via_resend

            return await send_via_resend(to, subject, body)
        from app.email.backends import send_to_console

        return await send_to_console(to, subject, body)
    except Exception:
        logger.warning("could not send %r to %s via %s", subject, to, backend, exc_info=True)
        return False
