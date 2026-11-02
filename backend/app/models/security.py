"""Records the API keeps about requests rather than about research."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.project import utcnow


class RateLimitHit(Base):
    """One counted attempt against a guarded action (sign-in, join code…).

    Kept in the database rather than in memory because serverless instances
    share nothing: an in-process counter resets on every cold start and is
    split across however many instances happen to be warm.
    """

    __tablename__ = "rate_limit_hits"
    __table_args__ = (Index("ix_rate_limit_hits_bucket_created", "bucket", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bucket: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PasswordResetToken(Base):
    """A one-time link emailed to someone who forgot their password.

    Only a SHA-256 hash of the token is stored, so someone who can read the
    database still cannot use a pending link. A token works once, within an
    hour, and requesting a new one cancels the old ones.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
