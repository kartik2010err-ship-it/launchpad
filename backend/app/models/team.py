"""Teams: a layer between a workspace and a project.

    Workspace -> Team -> Project

The shape that matters most here is what a team *is not*. A team is not a copy
of a project handed to three students. A team is an ownership mode: the project
row is the same row for everyone on it, and ``Project.owner_team_id`` points at
the team instead of ``Project.owner_id`` pointing at a person. Three students on
Team Coral all open the identical research question, timeline, poster and
notebook, because there is only one of each.

Individual contributions are tracked separately (``TeamContribution``) so a
student can say what *they* did at a judging interview without the app having to
fragment the project to represent it.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import TeamRole
from app.models.project import User, utcnow
from app.models.workspace_org import generate_join_code


def generate_team_code(name: str) -> str:
    """CORAL-8K2P.

    Same alphabet and shape as a workspace code, one word instead of two: a team
    code gets read out across a lab bench, not projected onto a screen.
    """

    words = [w for w in "".join(c if c.isalnum() else " " for c in name).split() if w]
    # "Team Coral" should give CORAL, not TEAM.
    meaningful = [w for w in words if w.lower() != "team"] or words
    return generate_join_code(" ".join(meaningful[:1]) or "TEAM")


class Team(Base):
    """A small group inside a workspace that shares one research project."""

    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_team_name_per_workspace"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, default=None)

    # Separate namespace from workspace codes: a student joins the workspace
    # first, then the team. The two codes are never interchangeable.
    join_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    # Off means the code is the only way in — the team stays unlisted.
    is_discoverable: Mapped[bool] = mapped_column(Boolean, default=True)

    mentor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None, index=True)

    # Which competition's team rules apply. Null falls back to the workspace's
    # own default; the resolved limit is computed in app.services.competitions.
    competition_key: Mapped[str | None] = mapped_column(String(60), default=None)
    # Per-team override of the competition maximum, for the case a coach has a
    # documented exception. Never silently larger than the competition allows
    # unless someone with authority set it here on purpose.
    max_members_override: Mapped[int | None] = mapped_column(Integer, default=None)
    # Competitions commonly freeze rosters at registration. Enforced, but only
    # described as this app's setting — never as official compliance.
    membership_locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    memberships: Mapped[list[TeamMembership]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )
    mentor: Mapped[User | None] = relationship(foreign_keys=[mentor_id])

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    @property
    def is_locked(self) -> bool:
        return self.membership_locked_at is not None


class TeamMembership(Base):
    """One student's place on one team."""

    __tablename__ = "team_memberships"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_membership"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[TeamRole] = mapped_column(String(20), default=TeamRole.MEMBER)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    team: Mapped[Team] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship()


class TeamContribution(Base):
    """Who did which part of the shared work.

    Hangs off the project rather than the team, because the project is the thing
    being judged and a contribution log is part of a science-fair notebook.
    """

    __tablename__ = "team_contributions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    task: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    contribution_date: Mapped[date | None] = mapped_column(Date, default=None)
    hours: Mapped[float | None] = mapped_column(Float, default=None)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Set when a mentor or lead asked for this rather than the student logging it.
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id])
