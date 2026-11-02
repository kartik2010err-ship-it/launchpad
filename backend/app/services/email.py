"""Outgoing email, through Resend's HTTP API.

One function, so the rest of the app never knows which provider is behind it,
and tests replace it with a list that records what would have been sent.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


def send_email(*, to: str, subject: str, text: str, html: str) -> bool:
    """Send one email. Returns whether it was handed to the provider.

    Never raises: a failed email is logged, and the caller decides what the
    person sees. For a password reset that is the same message either way.
    """

    settings = get_settings()
    if not settings.resend_api_key:
        log.warning("Email not sent to %s: RESEND_API_KEY is not configured", to)
        return False
    try:
        response = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={"from": settings.email_from, "to": [to], "subject": subject, "text": text, "html": html},
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        log.error("Email to %s failed: %s", to, exc)
        return False
    if response.status_code >= 400:
        log.error("Email to %s rejected by Resend (%s): %s", to, response.status_code, response.text[:300])
        return False
    return True
