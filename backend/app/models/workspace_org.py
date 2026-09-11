"""Workspaces: the container every project now lives inside.

The important architectural rule here is that authority is *relational*, not a
property of a person. A user row carries no power. A ``WorkspaceMembership``
row does, and only inside its own workspace. The same student can be a MEMBER
of their school's club, the LEAD of a robotics team, and the OWNER of their own
private space, all at once.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ProjectVisibility, WorkspaceRole, WorkspaceType
from app.models.project import User, utcnow

# Ambiguous characters (0/O, 1/I) are excluded: join codes get read aloud in a
# club meeting and typed by someone on a phone.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_join_code(name: str) -> str:
    """A code a teacher can say out loud: HAMILTON-SCIENCE-4F7K."""

    words = [w for w in "".join(c if c.isalnum() else " " for c in name).split() if w]
    prefix = "-".join(w.upper()[:9] for w in words[:2]) or "WORKSPACE"
    suffix = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(4))
    return f"{prefix}-{suffix}"


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    organization_name: Mapped[str | None] = mapped_column(String(200), default=None)
    workspace_type: Mapped[WorkspaceType] = mapped_column(
        String(40), default=WorkspaceType.RESEARCH_CLUB
    )
    description: Mapped[str | None] = mapped_column(Text, default=None)

    join_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    default_project_visibility: Mapped[ProjectVisibility] = mapped_column(
        String(20), default=ProjectVisibility.PRIVATE
    )
    # Leads can assign mentors unless the owner turns this off.
    leads_can_assign_mentors: Mapped[bool] = mapped_column(Boolean, default=True)
    # Section 5: a club where students organise themselves turns this on; a
    # classroom where the teacher assigns groups turns it off. Either way the
    # creator of a team joins it — there is no hidden "owner team" concept.
    members_can_create_teams: Mapped[bool] = mapped_column(Boolean, default=True)

    # A personal workspace is created automatically for every account so the
    # app works for a lone student who never joins a club.
    is_personal: Mapped[bool] = mapped_column(Boolean, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    memberships: Mapped[list[WorkspaceMembership]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


class WorkspaceMembership(Base):
    """One person's role inside one workspace. The unit of authorization."""

    __tablename__ = "workspace_memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_membership"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[WorkspaceRole] = mapped_column(String(20), default=WorkspaceRole.MEMBER)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    workspace: Mapped[Workspace] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship()


class WorkspaceInvitation(Base):
    """Either an emailed invite or a shareable link, both backed by a token."""

    __tablename__ = "workspace_invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    email: Mapped[str | None] = mapped_column(String(200), default=None, index=True)
    role: Mapped[WorkspaceRole] = mapped_column(String(20), default=WorkspaceRole.MEMBER)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    accepted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    workspace: Mapped[Workspace] = relationship()

    @staticmethod
    def new_token() -> str:
        return secrets.token_urlsafe(24)

    @staticmethod
    def default_expiry(days: int = 14) -> datetime:
        return utcnow() + timedelta(days=days)

    @property
    def is_usable(self) -> bool:
        if self.accepted_at is not None:
            return False
        expires = self.expires_at
        if expires.tzinfo is None:  # SQLite hands back naive datetimes
            expires = expires.replace(tzinfo=utcnow().tzinfo)
        return expires > utcnow()


class ProjectActivity(Base):
    """Append-only log powering the workspace feed.

    Denormalised on purpose: the feed renders thousands of rows and should not
    need to join four tables to say "Maya updated her research question".
    """

    __tablename__ = "project_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)

    actor_name: Mapped[str] = mapped_column(String(120), default="Someone")
    project_title: Mapped[str | None] = mapped_column(String(240), default=None)
    kind: Mapped[str] = mapped_column(String(30), default="project_change", index=True)
    action: Mapped[str] = mapped_column(String(60))
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
