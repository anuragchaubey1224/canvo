"""Where a message actually goes."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


async def send_to_console(to: str, subject: str, body: str) -> bool:
    """Print it. The default, so local development needs no provider and no secrets —
    the reset link is right there in the server log, which is also how you test the flow
    without a real inbox."""
    rule = "─" * 40
    logger.warning(
        "\n%s\nemail (console backend — not sent)\nTo: %s\nSubject: %s\n\n%s\n%s",
        rule,
        to,
        subject,
        body,
        rule,
    )
    return True


async def send_via_resend(to: str, subject: str, body: str) -> bool:
    """Resend's HTTP API. Chosen over SMTP because it needs no long-lived connection and
    no extra dependency beyond the HTTP client we already have."""
    import httpx

    key = os.getenv("RESEND_API_KEY", "").strip()
    sender = os.getenv("EMAIL_FROM", "").strip()
    if not key or not sender:
        logger.warning("EMAIL_BACKEND=resend but RESEND_API_KEY/EMAIL_FROM is unset")
        return False

    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {key}"},
            json={"from": sender, "to": [to], "subject": subject, "text": body},
        )
    if res.status_code >= 400:
        # No response body in the log: it echoes the recipient, and this line may end up
        # somewhere less private than the mailbox did.
        logger.warning("resend rejected a message (%s)", res.status_code)
        return False
    return True
