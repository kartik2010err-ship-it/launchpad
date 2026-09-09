from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import (
    Category,
    ProjectOwnerKind,
    ProjectStatus,
    ProjectType,
    ProjectVisibility,
    Role,
    Stage,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(String(20), default=Role.STUDENT)
    school: Mapped[str | None] = mapped_column(String(160), default=None)
    grade_level: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    projects: Mapped[list[Project]] = relationship(
        back_populates="owner", foreign_keys="Project.owner_id"
    )


class Project(Base):
    """One research project. Owned by exactly one student *or* one team.

    The two ownership columns are mutually exclusive and the database enforces
    it. A team project is not three projects that sync — it is one row, opened by
    every member, which is why joining a team never copies anything.
    """

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "(owner_id IS NOT NULL AND owner_team_id IS NULL)"
            " OR (owner_id IS NULL AND owner_team_id IS NOT NULL)",
            name="ck_project_single_owner",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Exactly one of these two is set; see the check constraint above.
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), default=None, index=True
    )
    owner_team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id"), default=None, index=True
    )
    # Every project lives in exactly one workspace; that membership is what
    # authorization is checked against.
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    mentor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None, index=True)
    visibility: Mapped[ProjectVisibility] = mapped_column(
        String(20), default=ProjectVisibility.PRIVATE
    )

    title: Mapped[str] = mapped_column(String(240))
    topic: Mapped[str | None] = mapped_column(Text, default=None)
    grade_level: Mapped[int] = mapped_column(Integer, default=9)
    project_type: Mapped[ProjectType] = mapped_column(String(20), default=ProjectType.SCIENTIFIC)
    category: Mapped[Category] = mapped_column(String(40), default=Category.OTHER)
    background_knowledge: Mapped[str | None] = mapped_column(Text, default=None)

    current_question: Mapped[str] = mapped_column(Text)
    stage: Mapped[Stage] = mapped_column(String(40), default=Stage.IDEA)

    # Competition context (section 16-18). Nullable until the student picks one.
    competition_key: Mapped[str | None] = mapped_column(String(60), default=None)
    competition_name: Mapped[str | None] = mapped_column(String(160), default=None)
    competition_date: Mapped[date | None] = mapped_column(Date, default=None)
    school_deadline: Mapped[date | None] = mapped_column(Date, default=None)
    hours_per_week: Mapped[float | None] = mapped_column(default=None)
    trials_planned: Mapped[int | None] = mapped_column(Integer, default=None)
    minutes_per_trial: Mapped[int | None] = mapped_column(Integer, default=None)
    teammates: Mapped[int] = mapped_column(Integer, default=0)
    already_experimenting: Mapped[bool] = mapped_column(default=False)

    # Derived by project_status_service, persisted so the workspace project
    # table can sort and filter on it without recomputing 200 rows.
    status: Mapped[ProjectStatus] = mapped_column(String(30), default=ProjectStatus.ON_TRACK)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    # Distinct from updated_at: a nightly status recompute must not make a
    # dormant project look active.
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped[User | None] = relationship(back_populates="projects", foreign_keys=[owner_id])
    mentor: Mapped[User | None] = relationship(foreign_keys=[mentor_id])
    owner_team: Mapped["Team | None"] = relationship(foreign_keys=[owner_team_id])  # noqa: F821
    revisions: Mapped[list[QuestionRevision]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="QuestionRevision.version"
    )
    interview_turns: Mapped[list[InterviewTurn]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="InterviewTurn.id"
    )

    @property
    def last_activity(self) -> datetime:
        return self.last_activity_at or self.updated_at

    @property
    def owner_kind(self) -> ProjectOwnerKind:
        return (
            ProjectOwnerKind.TEAM
            if self.owner_team_id is not None
            else ProjectOwnerKind.INDIVIDUAL
        )

    @property
    def is_team_project(self) -> bool:
        return self.owner_team_id is not None


class QuestionRevision(Base):
    """Section 10: the question's lineage, never overwritten in place."""

    __tablename__ = "question_revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    # Who produced it and what improved. "student" | "ai_refinement" | "mentor"
    source: Mapped[str] = mapped_column(String(30), default="student")
    variant: Mapped[str | None] = mapped_column(String(30), default=None)
    rationale: Mapped[str | None] = mapped_column(Text, default=None)
    improvements: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="revisions")


class InterviewTurn(Base):
    """One mentor question and, once answered, the student's reply."""

    __tablename__ = "interview_turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    question_key: Mapped[str] = mapped_column(String(60))
    question_text: Mapped[str] = mapped_column(Text)
    dimension: Mapped[str] = mapped_column(String(40))
    why_asked: Mapped[str | None] = mapped_column(Text, default=None)
    answer_text: Mapped[str | None] = mapped_column(Text, default=None)
    followup_note: Mapped[str | None] = mapped_column(Text, default=None)
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    project: Mapped[Project] = relationship(back_populates="interview_turns")
