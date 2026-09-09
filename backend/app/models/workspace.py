from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import CommentType, Phase, Priority, RequirementSource, TaskStatus
from app.models.project import utcnow


class Evaluation(Base):
    """A frozen snapshot of every score the engine produced at one moment.

    Scores are stored as JSON blobs rather than columns because the scoring
    schema evolves faster than the database. The Pydantic schemas in
    ``app.schemas.evaluation`` are the contract; this table is the archive, so
    a student can watch their readiness move over the season.
    """

    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    provider: Mapped[str] = mapped_column(String(40), default="heuristic")
    question_snapshot: Mapped[str] = mapped_column(Text)
    overall_score: Mapped[int] = mapped_column(Integer, default=0)
    information_completeness: Mapped[int] = mapped_column(Integer, default=0)

    dimensions: Mapped[dict] = mapped_column(JSON, default=dict)
    rubric: Mapped[dict] = mapped_column(JSON, default=dict)
    novelty: Mapped[dict] = mapped_column(JSON, default=dict)
    safety: Mapped[dict] = mapped_column(JSON, default=dict)
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    mentor_summary: Mapped[str] = mapped_column(Text, default="")
    next_actions: Mapped[list] = mapped_column(JSON, default=list)
    socratic_questions: Mapped[list] = mapped_column(JSON, default=list)


class ResearchPlan(Base):
    __tablename__ = "research_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    question: Mapped[str] = mapped_column(Text)
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(40), default="heuristic")


class MentorComment(Base):
    __tablename__ = "mentor_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    author_name: Mapped[str] = mapped_column(String(120), default="Mentor")
    # Workspace role at the time of writing, so the thread still reads correctly
    # after someone is promoted or steps down.
    author_role: Mapped[str] = mapped_column(String(20), default="mentor")
    section: Mapped[str] = mapped_column(String(60), default="general")
    comment_type: Mapped[CommentType] = mapped_column(String(20), default=CommentType.GENERAL)
    body: Mapped[str] = mapped_column(Text)
    requires_action: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TimelineTask(Base):
    __tablename__ = "timeline_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    key: Mapped[str] = mapped_column(String(80))
    phase: Mapped[Phase] = mapped_column(String(50))
    phase_index: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    start_date: Mapped[date | None] = mapped_column(Date, default=None)
    due_date: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[TaskStatus] = mapped_column(String(30), default=TaskStatus.NOT_STARTED)
    priority: Mapped[Priority] = mapped_column(String(20), default=Priority.MEDIUM)
    estimated_hours: Mapped[float] = mapped_column(default=1.0)
    depends_on: Mapped[list] = mapped_column(JSON, default=list)
    requirement_source: Mapped[RequirementSource] = mapped_column(
        String(50), default=RequirementSource.RECOMMENDED_CLUB_MILESTONE
    )
    ai_note: Mapped[str | None] = mapped_column(Text, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class NotebookEntry(Base):
    """Section 31. Entries are append-only by convention: edits are discouraged
    in the UI and amendments are added as new entries."""

    __tablename__ = "notebook_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    entry_date: Mapped[date] = mapped_column(Date)
    what_was_done: Mapped[str] = mapped_column(Text)
    procedure_changes: Mapped[str | None] = mapped_column(Text, default=None)
    observations: Mapped[str | None] = mapped_column(Text, default=None)
    problems: Mapped[str | None] = mapped_column(Text, default=None)
    raw_measurements: Mapped[str | None] = mapped_column(Text, default=None)
    open_questions: Mapped[str | None] = mapped_column(Text, default=None)
    next_steps: Mapped[str | None] = mapped_column(Text, default=None)
    attachments: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PosterDraft(Base):
    __tablename__ = "poster_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    layout_key: Mapped[str | None] = mapped_column(String(40), default=None)
    sections: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class MockJudgeSession(Base):
    __tablename__ = "mock_judge_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    transcript: Mapped[list] = mapped_column(JSON, default=list)
    report: Mapped[dict | None] = mapped_column(JSON, default=None)
    finished: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
