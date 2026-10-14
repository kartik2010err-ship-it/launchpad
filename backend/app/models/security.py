"""Records the API keeps about requests rather than about research."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String
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
