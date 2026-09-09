"""Professor and researcher outreach: drafts, sends, and what came back.

Rows belong to the student, not to a workspace. A student's correspondence with
a university lab is theirs; a club lead has no business reading it, so nothing
here is exposed through the workspace routes.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import OutreachStatus
from app.models.project import utcnow


class OutreachContact(Base):
    __tablename__ = "outreach_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Optional: which project this outreach is about.
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"), default=None, index=True
    )

    researcher_name: Mapped[str] = mapped_column(String(160))
    institution: Mapped[str | None] = mapped_column(String(200), default=None)
    email: Mapped[str | None] = mapped_column(String(200), default=None)
    # What of theirs the student actually read. The anti-spam field: a draft
    # cannot be generated without it.
    their_work: Mapped[str | None] = mapped_column(Text, default=None)

    template_key: Mapped[str | None] = mapped_column(String(60), default=None)
    subject: Mapped[str | None] = mapped_column(String(300), default=None)
    body: Mapped[str | None] = mapped_column(Text, default=None)

    status: Mapped[OutreachStatus] = mapped_column(String(30), default=OutreachStatus.DRAFT)
    sent_on: Mapped[date | None] = mapped_column(Date, default=None)
    follow_up_on: Mapped[date | None] = mapped_column(Date, default=None)
    follow_up_done: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
