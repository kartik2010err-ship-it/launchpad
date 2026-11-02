"""Forgot-password: issue a one-time emailed link, then accept a new password.

The rules, all enforced here rather than in the route:

* the raw token exists only in the email; the database keeps its SHA-256;
* a token works once and expires after ``password_reset_ttl_minutes``;
* asking again cancels every earlier unused token for that account;
* completing a reset stamps ``password_changed_at``, which signs out every
  session issued before it (see ``deps.current_user``).
"""

from __future__ import annotations

import hashlib
import html
import secrets
from datetime import timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.project import User, utcnow
from app.models.security import PasswordResetToken
from app.services.email import send_email


class InvalidResetToken(Exception):
    """The link is unknown, already used, or expired."""


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def reset_link(raw_token: str) -> str:
    base = get_settings().site_url.rstrip("/") or "http://localhost:5173"
    return f"{base}/reset-password?token={raw_token}"


def request_reset(db: Session, user: User) -> bool:
    """Create a fresh token for ``user`` and email the link. Returns whether
    the email was handed off."""

    settings = get_settings()
    now = utcnow()
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash(raw),
            expires_at=now + timedelta(minutes=settings.password_reset_ttl_minutes),
        )
    )
    db.commit()

    link = reset_link(raw)
    minutes = settings.password_reset_ttl_minutes
    name = user.name.split(" ")[0] if user.name else "there"
    text = (
        f"Hi {name},\n\n"
        f"Someone asked to reset the password for your Research Coach account. "
        f"If that was you, open this link to choose a new one:\n\n{link}\n\n"
        f"The link works once and expires in {minutes} minutes. If you didn't ask, "
        f"ignore this email and your password stays the same.\n"
    )
    safe_name, safe_link = html.escape(name), html.escape(link, quote=True)
    body = (
        f"<p>Hi {safe_name},</p>"
        f"<p>Someone asked to reset the password for your Research Coach account. "
        f"If that was you, choose a new one here:</p>"
        f'<p><a href="{safe_link}" style="display:inline-block;padding:10px 16px;'
        f'background:#4d9fff;color:#08111c;border-radius:4px;text-decoration:none">'
        f"Reset my password</a></p>"
        f"<p>Or paste this link into your browser:<br>{safe_link}</p>"
        f"<p>The link works once and expires in {minutes} minutes. If you didn't ask, "
        f"ignore this email and your password stays the same.</p>"
    )
    return send_email(to=user.email, subject="Reset your Research Coach password", text=text, html=body)


def complete_reset(db: Session, raw_token: str, new_password: str) -> User:
    """Set a new password from a valid link. Raises ``InvalidResetToken``."""

    token = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash(raw_token)))
    now = utcnow()
    if token is None or token.used_at is not None:
        raise InvalidResetToken
    expires = token.expires_at
    if expires.tzinfo is None:  # SQLite returns naive timestamps
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        raise InvalidResetToken
    user = db.get(User, token.user_id)
    if user is None:
        raise InvalidResetToken

    user.hashed_password = hash_password(new_password)
    user.password_changed_at = now
    token.used_at = now
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.commit()
    return user
