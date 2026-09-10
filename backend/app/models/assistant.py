"""The Research Assistant's memory: conversations and their messages.

Two rules shape this module.

*Privacy first.* A conversation belongs to one person. A student thinking out
loud about a project they share with two teammates is still thinking out loud,
and a workspace owner with oversight over every project does **not** get to read
what a student asked the assistant at 1am. Sharing is opt-in per conversation
(``shared_with_team``), never inherited from the project's visibility.

*Messages carry their citations.* When the assistant recommends a guide it
records the guide id on the message row, so the reference survives a page
reload and can be re-rendered from the library rather than from a URL frozen
into prose. Nothing in this table stores a link.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.project import User, utcnow


class AIConversation(Base):
    """One thread between a student and the Research Assistant."""

    __tablename__ = "ai_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Null for a general conversation opened outside any project. When set, the
    # assistant receives that project's structured context automatically.
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"), default=None, index=True
    )

    title: Mapped[str] = mapped_column(String(200), default="New conversation")

    # Opt-in. False means: only ``user_id`` may read this thread, whatever role
    # anyone else holds in the workspace.
    shared_with_team: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship()
    messages: Mapped[list["AIMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AIMessage.id",
    )


class AIMessage(Base):
    """One turn. ``role`` is "user" or "assistant"."""

    __tablename__ = "ai_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), default="user")
    content: Mapped[str] = mapped_column(Text)

    # Guide ids the assistant cited on this turn, resolved against
    # app.content.guides at render time. Stored as ids, never as URLs.
    guide_ids: Mapped[list] = mapped_column(JSON, default=list)
    # Follow-up questions the assistant asked, surfaced as one-tap replies.
    follow_ups: Mapped[list] = mapped_column(JSON, default=list)
    # Which provider produced an assistant turn, so a mixed thread stays honest.
    provider: Mapped[str | None] = mapped_column(String(40), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped[AIConversation] = relationship(back_populates="messages")
