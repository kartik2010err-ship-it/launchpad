"""Team routes, nested under the workspace that contains them.

Two things this file is careful about:

* A team join code never creates a project. It adds a membership row, and the
  team's existing shared project becomes visible because membership is what
  ``can_edit_project`` reads.
* Team codes and workspace codes are separate namespaces. Posting a workspace
  code here is a 404, not a quiet fallback.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    current_user,
    get_membership,
    get_team,
    get_workspace,
    require_oversight,
    require_team_manager,
)
from app.db.session import get_db
from app.models.enums import (
    ActivityKind,
    Category,
    ProjectType,
    Stage,
    TeamRole,
)
from app.models.project import Project, User
from app.models.team import Team, TeamContribution
from app.models.workspace import MentorComment, NotebookEntry, TimelineTask
from app.models.workspace_org import ProjectActivity, Workspace, WorkspaceMembership
from app.schemas.team import (
    ContributionCreate,
    ContributionOut,
    ContributionUpdate,
    TeamCreate,
    TeamDashboard,
    TeamJoinRequest,
    TeamLockUpdate,
    TeamMemberRoleUpdate,
    TeamMentorAssignment,
    TeamProjectCreate,
    TeamSummary,
    TeamUpdate,
)
from app.services import (
    activity_service,
    project_service,
    project_status_service,
    team_service,
    workspace_analytics,
    workspace_service,
)

router = APIRouter(prefix="/workspaces", tags=["teams"])


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #


def _may_see_code(db: Session, team: Team, membership: WorkspaceMembership) -> bool:
    """Members of the team and workspace oversight. Nobody else hands it out."""

    if workspace_service.is_oversight(membership):
        return True
    return team_service.is_team_member(db, team.id, membership.user_id)


def _summary(db: Session, team: Team, membership: WorkspaceMembership) -> dict:
    project = team_service.project_for_team(db, team.id)
    capacity = team_service.size_check(db, team)
    mentor = db.get(User, team.mentor_id) if team.mentor_id else None
    row = workspace_analytics.build_row(db, project) if project else None
    return {
        "id": team.id,
        "workspace_id": team.workspace_id,
        "name": team.name,
        "description": team.description,
        "join_code": team.join_code if _may_see_code(db, team, membership) else None,
        "is_discoverable": team.is_discoverable,
        "is_archived": team.is_archived,
        "membership_locked": team.is_locked,
        "mentor_id": team.mentor_id,
        "mentor_name": mentor.name if mentor else None,
        "competition_key": team.competition_key,
        "member_count": capacity["member_count"],
        "max_team_size": capacity["max_team_size"],
        "seats_left": capacity["seats_left"],
        "member_names": [m.name for m in team_service.members_of(db, team.id)],
        "project_id": project.id if project else None,
        "project_title": project.title if project else None,
        "readiness": row.readiness if row else None,
        "stage": row.stage if row else None,
        "status": str(row.status) if row else None,
        "next_deadline": row.next_deadline if row else None,
        "i_am_member": team_service.is_team_member(db, team.id, membership.user_id),
        "i_can_edit": team_service.can_edit_team_settings(db, team, membership),
        "created_at": team.created_at,
    }


def _contribution_out(db: Session, row: TeamContribution) -> dict:
    person = db.get(User, row.user_id)
    requester = db.get(User, row.requested_by_id) if row.requested_by_id else None
    return {
        "id": row.id,
        "project_id": row.project_id,
        "team_id": row.team_id,
        "user_id": row.user_id,
        "user_name": person.name if person else "Unknown",
        "task": row.task,
        "description": row.description,
        "contribution_date": row.contribution_date,
        "hours": row.hours,
        "completed": row.completed,
        "requested_by_id": row.requested_by_id,
        "requested_by_name": requester.name if requester else None,
        "created_at": row.created_at,
    }


# --------------------------------------------------------------------------- #
# Team lifecycle
# --------------------------------------------------------------------------- #


@router.get("/{workspace_id}/teams", response_model=list[TeamSummary])
def list_teams(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(get_membership),
    include_archived: bool = Query(default=False),
):
    """Teams in this workspace.

    Undiscoverable teams are hidden from members who are not on them — they are
    join-code-only — but never from oversight, which has to see everything.
    """

    teams = team_service.teams_in_workspace(db, workspace.id, include_archived=include_archived)
    out = []
    for team in teams:
        if (
            not team.is_discoverable
            and not workspace_service.is_oversight(membership)
            and not team_service.is_team_member(db, team.id, membership.user_id)
        ):
            continue
        out.append(_summary(db, team, membership))
    return out


@router.post(
    "/{workspace_id}/teams", response_model=TeamSummary, status_code=status.HTTP_201_CREATED
)
def create_team(
    payload: TeamCreate,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(get_membership),
    actor: User = Depends(current_user),
):
    if not team_service.can_create_teams(workspace, membership):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This workspace only lets owners and leads create teams.",
        )

    # A member who is not overseeing the workspace cannot create a team they are
    # not on: that would be organising other people's work from outside it.
    join_as_member = (
        payload.join_as_member
        if workspace_service.is_oversight(membership)
        else True
    )

    try:
        team = team_service.create_team(
            db,
            workspace=workspace,
            creator=actor,
            name=payload.name,
            description=payload.description,
            mentor_id=payload.mentor_id,
            competition_key=payload.competition_key,
            max_members_override=payload.max_members_override,
            is_discoverable=payload.is_discoverable,
            join_as_member=join_as_member,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    if payload.mentor_id is not None:
        try:
            team_service.assign_mentor(db, team, payload.mentor_id)
        except LookupError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    activity_service.record(
        db,
        project=None,
        actor=actor,
        action="team_created",
        summary=f"{actor.name} created {team.name}",
        kind=ActivityKind.MILESTONE,
        workspace_id=workspace.id,
    )
    db.commit()
    db.refresh(team)
    return _summary(db, team, membership)


@router.post("/{workspace_id}/teams/join", response_model=TeamSummary)
def join_team(
    payload: TeamJoinRequest,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(get_membership),
    actor: User = Depends(current_user),
):
    """Join a team with its own code. Never creates or copies a project."""

    try:
        team, _ = team_service.join_by_code(
            db, actor, payload.team_join_code, workspace_id=workspace.id
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc

    activity_service.record(
        db,
        project=None,
        actor=actor,
        action="team_joined",
        summary=f"{actor.name} joined {team.name}",
        kind=ActivityKind.MILESTONE,
        workspace_id=workspace.id,
    )
    db.commit()
    return _summary(db, team, membership)


@router.get("/{workspace_id}/teams/{team_id}", response_model=TeamSummary)
def read_team(
    db: Session = Depends(get_db),
    team: Team = Depends(get_team),
    membership: WorkspaceMembership = Depends(get_membership),
):
    return _summary(db, team, membership)


@router.patch("/{workspace_id}/teams/{team_id}", response_model=TeamSummary)
def update_team(
    payload: TeamUpdate,
    db: Session = Depends(get_db),
    team: Team = Depends(require_team_manager),
    membership: WorkspaceMembership = Depends(get_membership),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(team, field, value)
    db.commit()
    db.refresh(team)
    return _summary(db, team, membership)


@router.post("/{workspace_id}/teams/{team_id}/archive", response_model=TeamSummary)
def archive_team(
    db: Session = Depends(get_db),
    team: Team = Depends(get_team),
    membership: WorkspaceMembership = Depends(require_oversight),
):
    team_service.archive_team(db, team)
    db.commit()
    db.refresh(team)
    return _summary(db, team, membership)


@router.patch("/{workspace_id}/teams/{team_id}/mentor", response_model=TeamSummary)
def assign_team_mentor(
    payload: TeamMentorAssignment,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    team: Team = Depends(get_team),
    membership: WorkspaceMembership = Depends(get_membership),
):
    if not workspace_service.can_assign_mentor(workspace, membership):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot assign mentors here.")
    try:
        team_service.assign_mentor(db, team, payload.mentor_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    db.commit()
    db.refresh(team)
    return _summary(db, team, membership)


@router.patch("/{workspace_id}/teams/{team_id}/lock", response_model=TeamSummary)
def set_lock(
    payload: TeamLockUpdate,
    db: Session = Depends(get_db),
    team: Team = Depends(get_team),
    membership: WorkspaceMembership = Depends(require_oversight),
):
    """Freeze or unfreeze the roster.

    This is an application setting that mirrors how many fairs handle
    registration. It is not a statement that your registration is valid.
    """

    team_service.set_membership_lock(db, team, payload.locked)
    db.commit()
    db.refresh(team)
    return _summary(db, team, membership)


# --------------------------------------------------------------------------- #
# Team membership
# --------------------------------------------------------------------------- #


@router.post("/{workspace_id}/teams/{team_id}/members", response_model=TeamSummary)
def add_member(
    payload: dict,
    db: Session = Depends(get_db),
    team: Team = Depends(require_team_manager),
    membership: WorkspaceMembership = Depends(get_membership),
):
    user_id = payload.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "user_id is required.")
    person = db.get(User, user_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That person does not exist.")
    try:
        team_service.add_team_member(db, team, person)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.commit()
    db.refresh(team)
    return _summary(db, team, membership)


@router.patch(
    "/{workspace_id}/teams/{team_id}/members/{user_id}", response_model=TeamSummary
)
def set_member_role(
    user_id: int,
    payload: TeamMemberRoleUpdate,
    db: Session = Depends(get_db),
    team: Team = Depends(require_team_manager),
    membership: WorkspaceMembership = Depends(get_membership),
):
    try:
        team_service.set_member_role(db, team, user_id, payload.role)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    db.commit()
    db.refresh(team)
    return _summary(db, team, membership)


@router.delete(
    "/{workspace_id}/teams/{team_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_member(
    user_id: int,
    db: Session = Depends(get_db),
    team: Team = Depends(get_team),
    membership: WorkspaceMembership = Depends(get_membership),
    actor: User = Depends(current_user),
):
    """A manager can remove anyone; a student can remove themselves."""

    leaving_self = user_id == actor.id
    if not leaving_self and not team_service.can_edit_team_settings(db, team, membership):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only a team or workspace lead can remove someone."
        )
    try:
        team_service.remove_team_member(db, team, user_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    db.commit()


# --------------------------------------------------------------------------- #
# The one shared project
# --------------------------------------------------------------------------- #


@router.post(
    "/{workspace_id}/teams/{team_id}/project",
    status_code=status.HTTP_201_CREATED,
)
def create_team_project(
    payload: TeamProjectCreate,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    team: Team = Depends(get_team),
    membership: WorkspaceMembership = Depends(get_membership),
    actor: User = Depends(current_user),
):
    """Start the team's single shared research project.

    Team-owned from the first row: ``owner_id`` stays null and ``owner_team_id``
    carries the ownership, so no member is privileged over the others.
    """

    if not (
        team_service.is_team_member(db, team.id, actor.id)
        or team_service.can_edit_team_settings(db, team, membership)
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Join the team before starting its project."
        )
    if team_service.project_for_team(db, team.id) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{team.name} already has a shared project. A team owns exactly one.",
        )

    project = Project(
        owner_id=None,
        owner_team_id=team.id,
        workspace_id=workspace.id,
        mentor_id=team.mentor_id,
        visibility=workspace.default_project_visibility,
        title=payload.title,
        topic=payload.topic,
        grade_level=payload.grade_level,
        project_type=ProjectType(payload.project_type),
        category=Category(payload.category),
        background_knowledge=payload.background_knowledge,
        current_question=payload.initial_question,
        stage=Stage.IDEA,
        competition_key=team.competition_key,
        teammates=max(0, team_service.member_count(db, team.id) - 1),
    )
    db.add(project)
    db.flush()
    project_service.add_revision(
        db, project, payload.initial_question, source="student",
        rationale="The team's starting question, kept for the record.",
    )
    project_service.advance_interview(db, project, [], max_questions=3)
    project_status_service.refresh(db, project)
    activity_service.record(
        db,
        project=project,
        actor=actor,
        action="project_created",
        summary=f"{team.name} started {project.title}",
        kind=ActivityKind.MILESTONE,
    )
    db.commit()
    db.refresh(project)
    return {"project_id": project.id, "title": project.title, "team_id": team.id}


# --------------------------------------------------------------------------- #
# Contributions
# --------------------------------------------------------------------------- #


def _require_team_project(db: Session, team: Team) -> Project:
    project = team_service.project_for_team(db, team.id)
    if project is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "This team has not started its shared project yet."
        )
    return project


@router.get(
    "/{workspace_id}/teams/{team_id}/contributions", response_model=list[ContributionOut]
)
def list_contributions(
    db: Session = Depends(get_db),
    team: Team = Depends(get_team),
    membership: WorkspaceMembership = Depends(get_membership),
):
    project = _require_team_project(db, team)
    if not workspace_service.can_view_project(db, project, membership):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot open this team's project.")
    return [
        _contribution_out(db, row)
        for row in team_service.contributions_for_project(db, project.id)
    ]


@router.post(
    "/{workspace_id}/teams/{team_id}/contributions",
    response_model=ContributionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_contribution(
    payload: ContributionCreate,
    db: Session = Depends(get_db),
    team: Team = Depends(get_team),
    membership: WorkspaceMembership = Depends(get_membership),
    actor: User = Depends(current_user),
):
    project = _require_team_project(db, team)
    target_id = payload.user_id or actor.id
    if not team_service.can_log_contribution(db, team, membership, target_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You can log your own contributions; mentors and leads can log or request anyone's.",
        )
    if not team_service.is_team_member(db, team.id, target_id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "That person is not on this team."
        )

    row = TeamContribution(
        project_id=project.id,
        team_id=team.id,
        user_id=target_id,
        task=payload.task,
        description=payload.description,
        contribution_date=payload.contribution_date or date.today(),
        hours=payload.hours,
        completed=payload.completed,
        requested_by_id=actor.id if target_id != actor.id else None,
    )
    db.add(row)
    activity_service.record(
        db,
        project=project,
        actor=actor,
        action="contribution_logged",
        summary=f"{actor.name} logged team work: {payload.task}",
        kind=ActivityKind.PROJECT_CHANGE,
    )
    db.commit()
    db.refresh(row)
    return _contribution_out(db, row)


@router.patch(
    "/{workspace_id}/teams/{team_id}/contributions/{contribution_id}",
    response_model=ContributionOut,
)
def update_contribution(
    contribution_id: int,
    payload: ContributionUpdate,
    db: Session = Depends(get_db),
    team: Team = Depends(get_team),
    membership: WorkspaceMembership = Depends(get_membership),
):
    row = db.get(TeamContribution, contribution_id)
    if row is None or row.team_id != team.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contribution not found.")
    if not team_service.can_log_contribution(db, team, membership, row.user_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot change that entry.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return _contribution_out(db, row)


@router.delete(
    "/{workspace_id}/teams/{team_id}/contributions/{contribution_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_contribution(
    contribution_id: int,
    db: Session = Depends(get_db),
    team: Team = Depends(get_team),
    membership: WorkspaceMembership = Depends(get_membership),
):
    row = db.get(TeamContribution, contribution_id)
    if row is None or row.team_id != team.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contribution not found.")
    if not team_service.can_log_contribution(db, team, membership, row.user_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot delete that entry.")
    db.delete(row)
    db.commit()


# --------------------------------------------------------------------------- #
# Team dashboard
# --------------------------------------------------------------------------- #


@router.get("/{workspace_id}/teams/{team_id}/dashboard", response_model=TeamDashboard)
def team_dashboard(
    db: Session = Depends(get_db),
    team: Team = Depends(get_team),
    membership: WorkspaceMembership = Depends(get_membership),
):
    """One screen showing what everyone on the team is working on."""

    project = team_service.project_for_team(db, team.id)
    can_view = project is not None and workspace_service.can_view_project(
        db, project, membership
    )
    can_edit = project is not None and workspace_service.can_edit_project(
        db, project, membership
    )

    rollup = {
        r["user_id"]: r
        for r in (team_service.contribution_summary(db, project.id) if project else [])
    }
    members = []
    for tm in team_service.memberships_of(db, team.id):
        person = db.get(User, tm.user_id)
        if person is None:
            continue
        stats = rollup.get(person.id, {"tasks": 0, "completed": 0, "hours": 0.0})
        members.append(
            {
                "user_id": person.id,
                "name": person.name,
                "email": person.email,
                "role": tm.role,
                "joined_at": tm.joined_at,
                "contribution_count": stats["tasks"],
                "completed_count": stats["completed"],
                "hours": stats["hours"],
            }
        )

    tasks: list[dict] = []
    notebook: list[dict] = []
    comments: list[dict] = []
    contributions: list[dict] = []
    activity: list[dict] = []
    project_payload = None

    if project is not None and can_view:
        row = workspace_analytics.build_row(db, project)
        project_payload = {
            "id": project.id,
            "title": project.title,
            "current_question": project.current_question,
            "stage": str(project.stage),
            "status": str(row.status),
            "readiness": row.readiness,
            "category": str(project.category),
            "project_type": str(project.project_type),
            "competition_name": project.competition_name,
            "competition_date": project.competition_date,
            "days_to_competition": row.days_to_competition,
            "next_deadline": row.next_deadline,
            "next_task": row.next_task,
            "mentor_name": row.mentor_name,
            "visibility": str(project.visibility),
        }
        tasks = [
            {
                "id": t.id,
                "title": t.title,
                "phase": str(t.phase),
                "status": str(t.status),
                "due_date": t.due_date,
                "priority": str(t.priority),
            }
            for t in db.scalars(
                select(TimelineTask)
                .where(TimelineTask.project_id == project.id)
                .order_by(TimelineTask.phase_index, TimelineTask.id)
            )
        ]
        notebook = [
            {
                "id": n.id,
                "entry_date": n.entry_date,
                "what_was_done": n.what_was_done,
                "observations": n.observations,
                "created_at": n.created_at,
            }
            for n in db.scalars(
                select(NotebookEntry)
                .where(NotebookEntry.project_id == project.id)
                .order_by(NotebookEntry.entry_date.desc())
                .limit(10)
            )
        ]
        comments = [
            {
                "id": c.id,
                "author_name": c.author_name,
                "author_role": c.author_role,
                "body": c.body,
                "comment_type": str(c.comment_type),
                "requires_action": c.requires_action,
                "resolved": c.resolved,
                "created_at": c.created_at,
            }
            for c in db.scalars(
                select(MentorComment)
                .where(MentorComment.project_id == project.id)
                .order_by(MentorComment.created_at.desc())
            )
        ]
        contributions = [
            _contribution_out(db, r)
            for r in team_service.contributions_for_project(db, project.id)
        ]
        activity = [
            {
                "id": a.id,
                "actor_name": a.actor_name,
                "kind": a.kind,
                "action": a.action,
                "summary": a.summary,
                "created_at": a.created_at,
            }
            for a in db.scalars(
                select(ProjectActivity)
                .where(ProjectActivity.project_id == project.id)
                .order_by(ProjectActivity.created_at.desc())
                .limit(15)
            )
        ]

    return {
        "team": _summary(db, team, membership),
        "members": members,
        "capacity": team_service.size_check(db, team),
        "can_edit_project": can_edit,
        "can_manage_team": team_service.can_edit_team_settings(db, team, membership),
        "project": project_payload,
        "tasks": tasks,
        "contributions": contributions,
        "contribution_rollup": list(rollup.values()),
        "notebook": notebook,
        "comments": comments,
        "activity": activity,
    }
