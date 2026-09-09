"""API contracts for teams, team membership and shared-project contributions."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RequirementSource, TeamRole


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Competition-configured team rules
# --------------------------------------------------------------------------- #


class CompetitionTeamRules(BaseModel):
    """How this app is configured — deliberately not a compliance claim."""

    competition_key: str
    competition_name: str
    teams_allowed: bool
    max_team_size: int
    min_team_size: int
    lock_membership_after_registration: bool
    divisions: list[str]
    source: RequirementSource
    official_source_loaded: bool
    notice: str


class TeamCapacity(BaseModel):
    member_count: int
    max_team_size: int
    seats_left: int
    is_full: bool
    limit_source: str
    membership_locked: bool
    rules: CompetitionTeamRules
    notice: str


# --------------------------------------------------------------------------- #
# Teams
# --------------------------------------------------------------------------- #


class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    mentor_id: int | None = None
    competition_key: str | None = None
    max_members_override: int | None = Field(default=None, ge=1, le=12)
    is_discoverable: bool = True


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = None
    competition_key: str | None = None
    max_members_override: int | None = Field(default=None, ge=1, le=12)
    is_discoverable: bool | None = None


class TeamMemberOut(BaseModel):
    user_id: int
    name: str
    email: str
    role: TeamRole
    joined_at: datetime
    contribution_count: int = 0
    completed_count: int = 0
    hours: float = 0.0


class TeamSummary(BaseModel):
    id: int
    workspace_id: int
    name: str
    description: str | None
    # Withheld from people who are neither on the team nor overseeing it.
    join_code: str | None = None
    is_discoverable: bool
    is_archived: bool
    membership_locked: bool
    mentor_id: int | None
    mentor_name: str | None
    competition_key: str | None
    member_count: int
    max_team_size: int
    seats_left: int
    member_names: list[str]
    project_id: int | None
    project_title: str | None
    readiness: int | None
    stage: str | None
    status: str | None
    next_deadline: date | None
    i_am_member: bool
    created_at: datetime


class TeamJoinRequest(BaseModel):
    # Separate field name from the workspace one so a mis-posted body fails
    # loudly instead of joining the wrong kind of thing.
    team_join_code: str = Field(min_length=3, max_length=40)


class TeamMemberRoleUpdate(BaseModel):
    role: TeamRole


class TeamMentorAssignment(BaseModel):
    mentor_id: int | None


class TeamLockUpdate(BaseModel):
    locked: bool


class TeamProjectCreate(BaseModel):
    """Create the team's one shared project.

    Fails if the team already has one: a team owns a single project by design.
    """

    title: str = Field(min_length=3, max_length=240)
    initial_question: str = Field(min_length=5)
    topic: str | None = None
    grade_level: int = Field(default=10, ge=5, le=12)
    project_type: str = "scientific"
    category: str = "other"
    background_knowledge: str | None = None


# --------------------------------------------------------------------------- #
# Contributions
# --------------------------------------------------------------------------- #


class ContributionCreate(BaseModel):
    user_id: int | None = None  # defaults to the caller
    task: str = Field(min_length=2, max_length=200)
    description: str | None = None
    contribution_date: date | None = None
    hours: float | None = Field(default=None, ge=0, le=500)
    completed: bool = False


class ContributionUpdate(BaseModel):
    task: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    contribution_date: date | None = None
    hours: float | None = Field(default=None, ge=0, le=500)
    completed: bool | None = None


class ContributionOut(ORMModel):
    id: int
    project_id: int
    team_id: int
    user_id: int
    user_name: str
    task: str
    description: str | None
    contribution_date: date | None
    hours: float | None
    completed: bool
    requested_by_id: int | None
    requested_by_name: str | None
    created_at: datetime


class ContributionRollup(BaseModel):
    user_id: int
    name: str
    tasks: int
    completed: int
    hours: float


# --------------------------------------------------------------------------- #
# Team dashboard
# --------------------------------------------------------------------------- #


class TeamTask(BaseModel):
    id: int
    title: str
    phase: str
    status: str
    due_date: date | None
    priority: str


class TeamNotebookEntry(BaseModel):
    id: int
    entry_date: date
    what_was_done: str
    observations: str | None
    created_at: datetime


class TeamComment(BaseModel):
    id: int
    author_name: str
    author_role: str
    body: str
    comment_type: str
    requires_action: bool
    resolved: bool
    created_at: datetime


class TeamActivity(BaseModel):
    id: int
    actor_name: str
    kind: str
    action: str
    summary: str
    created_at: datetime


class TeamDashboard(BaseModel):
    team: TeamSummary
    members: list[TeamMemberOut]
    capacity: TeamCapacity
    can_edit_project: bool
    can_manage_team: bool
    project: dict | None
    tasks: list[TeamTask]
    contributions: list[ContributionOut]
    contribution_rollup: list[ContributionRollup]
    notebook: list[TeamNotebookEntry]
    comments: list[TeamComment]
    activity: list[TeamActivity]
