from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    Category,
    NoveltyStatus,
    Phase,
    Priority,
    ProjectType,
    RequirementSource,
    Stage,
    TaskStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


# --------------------------------------------------------------------------- #
# Projects
# --------------------------------------------------------------------------- #


class ProjectCreate(BaseModel):
    # Omit to drop the project into the caller's personal workspace.
    workspace_id: int | None = None
    title: str = Field(min_length=3, max_length=240)
    topic: str | None = None
    initial_question: str = Field(min_length=5)
    grade_level: int = Field(ge=5, le=12)
    project_type: ProjectType
    category: Category
    background_knowledge: str | None = None


class ProjectUpdate(BaseModel):
    title: str | None = None
    topic: str | None = None
    stage: Stage | None = None
    category: Category | None = None
    background_knowledge: str | None = None
    competition_key: str | None = None
    competition_name: str | None = None
    competition_date: date | None = None
    school_deadline: date | None = None
    hours_per_week: float | None = None
    trials_planned: int | None = None
    minutes_per_trial: int | None = None
    teammates: int | None = None
    already_experimenting: bool | None = None


class QuestionRevisionOut(ORMModel):
    id: int
    version: int
    text: str
    source: str
    variant: str | None
    rationale: str | None
    improvements: list[str]
    created_at: datetime


class InterviewTurnOut(ORMModel):
    id: int
    question_key: str
    question_text: str
    dimension: str
    why_asked: str | None
    answer_text: str | None
    followup_note: str | None
    asked_at: datetime
    answered_at: datetime | None


class ProjectSummary(ORMModel):
    id: int
    workspace_id: int
    mentor_id: int | None = None
    visibility: str = "private"
    status: str = "on_track"
    title: str
    owner_id: int | None = None
    owner_team_id: int | None = None
    owner_kind: str = "individual"
    grade_level: int
    project_type: ProjectType
    category: Category
    stage: Stage
    current_question: str
    competition_name: str | None
    competition_date: date | None
    updated_at: datetime


class ProjectDetail(ProjectSummary):
    topic: str | None
    background_knowledge: str | None
    competition_key: str | None
    school_deadline: date | None
    hours_per_week: float | None
    trials_planned: int | None
    minutes_per_trial: int | None
    teammates: int
    already_experimenting: bool
    created_at: datetime
    revisions: list[QuestionRevisionOut] = []
    interview_turns: list[InterviewTurnOut] = []


# --------------------------------------------------------------------------- #
# Interview
# --------------------------------------------------------------------------- #


class InterviewAnswer(BaseModel):
    question_key: str
    answer: str


class InterviewSubmission(BaseModel):
    answers: list[InterviewAnswer] = Field(default_factory=list)
    max_questions: int = Field(default=3, ge=1, le=6)


# --------------------------------------------------------------------------- #
# Evaluation records
# --------------------------------------------------------------------------- #


class EvaluationOut(ORMModel):
    id: int
    project_id: int
    created_at: datetime
    provider: str
    question_snapshot: str
    overall_score: int
    information_completeness: int
    dimensions: list
    rubric: dict
    novelty: dict
    safety: dict
    mentor_summary: str
    next_actions: list
    socratic_questions: list = []


class ScoreHistoryPoint(BaseModel):
    created_at: datetime
    overall_score: int
    dimensions: dict[str, int]


# --------------------------------------------------------------------------- #
# Refinement / plan
# --------------------------------------------------------------------------- #


class SelectVariant(BaseModel):
    question: str
    variant: str | None = None
    rationale: str | None = None
    improvements: list[str] = Field(default_factory=list)


class ResearchPlanOut(ORMModel):
    id: int
    project_id: int
    created_at: datetime
    question: str
    content: dict
    provider: str


# --------------------------------------------------------------------------- #
# Mentor
# --------------------------------------------------------------------------- #


class MentorCommentCreate(BaseModel):
    body: str = Field(min_length=1)
    section: str = "general"
    requires_action: bool = False


class MentorCommentOut(ORMModel):
    id: int
    project_id: int
    author_name: str
    section: str
    body: str
    requires_action: bool
    resolved: bool
    created_at: datetime


class MentorRow(BaseModel):
    project_id: int
    student_name: str
    grade_level: int
    title: str
    category: Category
    project_type: ProjectType
    current_question: str
    stage: Stage
    readiness: int | None
    novelty_status: NoveltyStatus | None
    feasibility: int | None
    rubric_question_points: int | None
    safety_flags: list[str]
    open_comments: int
    last_activity: datetime


# --------------------------------------------------------------------------- #
# Timeline
# --------------------------------------------------------------------------- #


class TimelineTaskOut(ORMModel):
    id: int
    key: str
    phase: Phase
    phase_index: int
    title: str
    description: str | None
    start_date: date | None
    due_date: date | None
    status: TaskStatus
    priority: Priority
    estimated_hours: float
    depends_on: list
    requirement_source: RequirementSource
    ai_note: str | None


class TimelineTaskUpdate(BaseModel):
    status: TaskStatus | None = None
    due_date: date | None = None
    priority: Priority | None = None


class TimelineRequest(BaseModel):
    competition_key: str
    competition_name: str | None = None
    competition_date: date
    school_deadline: date | None = None
    hours_per_week: float = Field(gt=0, le=60)
    trials_planned: int | None = None
    minutes_per_trial: int | None = None
    teammates: int = 0
    already_experimenting: bool = False


class TimelineWarning(BaseModel):
    severity: str
    message: str
    recommendation: str


class TimelineOut(BaseModel):
    tasks: list[TimelineTaskOut]
    warnings: list[TimelineWarning]
    total_estimated_hours: float
    available_hours: float
    days_remaining: int
    competition_name: str | None
    competition_date: date | None
    requirement_disclaimer: str


class ReadinessArea(BaseModel):
    key: str
    label: str
    percent: int
    note: str


class ReadinessOut(BaseModel):
    areas: list[ReadinessArea]
    overall: int
    disclaimer: str


class WeeklyPlan(BaseModel):
    priorities: list[TimelineTaskOut]
    upcoming_deadline: date | None
    days_remaining: int | None
    completion_percent: int
    blockers: list[TimelineTaskOut]
    mentor_requests: list[MentorCommentOut]
    risk_notes: list[str]


# --------------------------------------------------------------------------- #
# Notebook / poster
# --------------------------------------------------------------------------- #


class NotebookEntryCreate(BaseModel):
    entry_date: date
    what_was_done: str
    procedure_changes: str | None = None
    observations: str | None = None
    problems: str | None = None
    raw_measurements: str | None = None
    open_questions: str | None = None
    next_steps: str | None = None


class NotebookEntryOut(NotebookEntryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class PosterDraftUpdate(BaseModel):
    layout_key: str | None = None
    sections: dict[str, str] = Field(default_factory=dict)


class PosterDraftOut(ORMModel):
    id: int
    project_id: int
    layout_key: str | None
    sections: dict
    updated_at: datetime


class MockJudgeMessage(BaseModel):
    answer: str | None = None
    finish: bool = False
