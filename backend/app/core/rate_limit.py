"""Database-backed attempt limits for the endpoints worth guessing against.

Sign-in, sign-up and workspace join codes are the three places where a script
can make progress by trying values. A join code has only four random
characters after a guessable prefix, and passwords are whatever students pick,
so each of these gets a per-client budget per window.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.project import utcnow
from app.models.security import RateLimitHit


def client_ip(request: Request) -> str:
    """The caller's address. Behind Vercel the socket peer is the edge, so
    the first ``X-Forwarded-For`` hop (which Vercel overwrites, not appends to
    a client-supplied value) is the real client."""

    if get_settings().is_serverless:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _window_start():
    return utcnow() - timedelta(seconds=get_settings().auth_rate_window_seconds)


# A school network puts a whole classroom behind one address, so buckets keyed
# by IP get a bigger budget than buckets keyed by one account or one user.
SHARED_ADDRESS_FACTOR = 5


def _limit_for(bucket: str, base: int) -> int:
    return base * SHARED_ADDRESS_FACTOR if bucket.startswith(("ip:", "login-ip:", "register:")) else base


def check(db: Session, *buckets: str) -> None:
    """Refuse with 429 when any bucket has used up its attempts."""

    base = get_settings().auth_rate_limit
    if base <= 0:
        return
    since = _window_start()
    for bucket in buckets:
        limit = _limit_for(bucket, base)
        used = db.scalar(
            select(func.count())
            .select_from(RateLimitHit)
            .where(RateLimitHit.bucket == bucket, RateLimitHit.created_at >= since)
        )
        if (used or 0) >= limit:
            minutes = max(1, get_settings().auth_rate_window_seconds // 60)
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Too many attempts. Wait {minutes} minutes and try again.",
            )


def record(db: Session, *buckets: str) -> None:
    """Count an attempt against each bucket, and sweep expired rows.

    Commits on its own so a failed attempt is counted even though the request
    that made it is about to raise.
    """

    if get_settings().auth_rate_limit <= 0:
        return
    db.execute(delete(RateLimitHit).where(RateLimitHit.created_at < _window_start()))
    db.add_all(RateLimitHit(bucket=bucket[:200]) for bucket in buckets)
    db.commit()
