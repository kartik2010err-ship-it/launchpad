"""API contracts for everything workspace-scoped."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import (
    CommentType,
    ProjectStatus,
    ProjectVisibility,
    WorkspaceRole,
    WorkspaceType,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Workspaces
# --------------------------------------------------------------------------- #


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    organization_name: str | None = Field(default=None, max_length=200)
    workspace_type: WorkspaceType = WorkspaceType.RESEARCH_CLUB
    description: str | None = None
    default_project_visibility: ProjectVisibility = ProjectVisibility.PRIVATE


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    organization_name: str | None = None
    workspace_type: WorkspaceType | None = None
    description: str | None = None
    default_project_visibility: ProjectVisibility | None = None
    leads_can_assign_mentors: bool | None = None
    members_can_create_teams: bool | None = None


class WorkspaceSummary(ORMModel):
    id: int
    name: str
    organization_name: str | None
    workspace_type: WorkspaceType
    description: str | None
    is_personal: bool
    is_archived: bool
    # The caller's own role here — the frontend needs it to decide what to show,
    # though the backend never trusts that decision.
    my_role: WorkspaceRole
    member_count: int
    project_count: int


class WorkspaceDetail(WorkspaceSummary):
    join_code: str | None = None  # withheld from plain members
    default_project_visibility: ProjectVisibility
    leads_can_assign_mentors: bool
    members_can_create_teams: bool = True
    created_at: datetime


class JoinRequest(BaseModel):
    join_code: str = Field(min_length=3, max_length=40)


class TeamRef(BaseModel):
    id: int
    name: str


class MemberOut(BaseModel):
    user_id: int
    name: str
    email: str
    role: WorkspaceRole
    joined_at: datetime
    project_count: int
    mentoring_count: int
    last_activity: date | None
    teams: list[TeamRef] = []


class RoleUpdate(BaseModel):
    role: WorkspaceRole


class InvitationCreate(BaseModel):
    email: EmailStr | None = None
    role: WorkspaceRole = WorkspaceRole.MEMBER


class InvitationOut(ORMModel):
    id: int
    email: str | None
    role: WorkspaceRole
    token: str
    expires_at: datetime
    accepted_at: datetime | None


class AcceptInvitation(BaseModel):
    token: str


# --------------------------------------------------------------------------- #
# Project overview
# --------------------------------------------------------------------------- #


class WorkspaceProjectRow(BaseModel):
    project_id: int
    title: str
    # Null on a team project; ``owner_name`` is then the team's name and
    # ``member_names`` lists who is on it.
    owner_id: int | None = None
    owner_name: str
    owner_kind: str = "individual"
    team_id: int | None = None
    team_name: str | None = None
    member_names: list[str] = []
    category: str
    project_type: str
    stage: str
    current_question: str
    competition_name: str | None
    competition_date: date | None
    days_to_competition: int | None
    readiness: int | None
    research_question_score: int | None
    methodology_score: int | None
    feasibility_score: int | None
    novelty_status: str | None
    approval_status: str
    safety_flags: list[str]
    experimentation_percent: int
    poster_percent: int
    interview_percent: int
    methodology_percent: int
    next_deadline: date | None
    next_task: str | None
    last_activity: date | None
    days_inactive: int
    mentor_id: int | None
    mentor_name: str | None
    status: ProjectStatus
    reasons: list[str]
    blockers: list[str]
    open_comments: int


class AttentionProject(BaseModel):
    project_id: int
    title: str
    owner_name: str
    detail: str


class AttentionGroup(BaseModel):
    key: str
    severity: str
    label: str
    projects: list[AttentionProject]


class MentorWorkload(BaseModel):
    user_id: int
    name: str
    email: str
    assigned_projects: int
    needing_review: int
    at_risk: int


class WorkspaceSummaryStats(BaseModel):
    total_projects: int
    active_projects: int
    on_track: int
    needs_attention: int
    at_risk: int
    blocked: int
    complete: int
    awaiting_approval: int
    needing_mentor_review: int
    without_mentor: int
    near_deadline: int
    average_readiness: int | None
    by_stage: dict[str, int]
    by_category: dict[str, int]
    average_poster: int
    average_interview: int


class UpcomingDeadline(BaseModel):
    project_id: int
    title: str
    owner_name: str
    label: str
    due: date
    days_away: int


class ActivityOut(ORMModel):
    id: int
    project_id: int | None
    project_title: str | None
    actor_name: str
    kind: str
    action: str
    summary: str
    created_at: datetime


class WorkspaceDashboard(BaseModel):
    workspace: WorkspaceDetail
    stats: WorkspaceSummaryStats
    attention: list[AttentionGroup]
    upcoming_deadlines: list[UpcomingDeadline]
    mentors: list[MentorWorkload]
    competitions: list[str]
    recent_activity: list[ActivityOut]


class ProgressArea(BaseModel):
    key: str
    label: str
    percent: int
    note: str


class StudentProgress(BaseModel):
    areas: list[ProgressArea]
    overall: int
    current_priority: str | None
    next_deadline: date | None
    days_to_next_deadline: int | None
    current_risk: str | None
    status: ProjectStatus


class MentorAssignment(BaseModel):
    mentor_id: int | None


class VisibilityUpdate(BaseModel):
    visibility: ProjectVisibility


class WorkspaceCommentCreate(BaseModel):
    body: str = Field(min_length=1)
    section: str = "general"
    comment_type: CommentType = CommentType.GENERAL


class WorkspaceCommentOut(ORMModel):
    id: int
    project_id: int
    author_id: int | None
    author_name: str
    author_role: str
    section: str
    comment_type: CommentType
    body: str
    requires_action: bool
    resolved: bool
    created_at: datetime
