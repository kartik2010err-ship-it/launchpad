"""Workspace routes.

Handlers stay thin: they resolve scope through dependencies, call a service,
and shape the response. No club-lead business logic lives in this file.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    current_user,
    get_membership,
    get_project,
    get_workspace,
    require_oversight,
    require_owner,
)
from app.db.session import get_db
from app.models.enums import ActivityKind, CommentType, ProjectStatus, WorkspaceRole
from app.models.project import Project, User
from app.models.workspace import MentorComment
from app.models.workspace_org import Workspace, WorkspaceMembership
from app.schemas.workspace import (
    AcceptInvitation,
    ActivityOut,
    AttentionGroup,
    InvitationCreate,
    InvitationOut,
    JoinRequest,
    MemberOut,
    MentorAssignment,
    RoleUpdate,
    StudentProgress,
    VisibilityUpdate,
    WorkspaceCommentCreate,
    WorkspaceCommentOut,
    WorkspaceCreate,
    WorkspaceDashboard,
    WorkspaceDetail,
    WorkspaceProjectRow,
    WorkspaceSummary,
    WorkspaceSummaryStats,
    WorkspaceUpdate,
)
from app.services import activity_service, workspace_analytics, workspace_service

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


# --------------------------------------------------------------------------- #
# Serialisation helpers
# --------------------------------------------------------------------------- #


def _summary(db: Session, workspace: Workspace, membership: WorkspaceMembership) -> dict:
    return {
        "id": workspace.id,
        "name": workspace.name,
        "organization_name": workspace.organization_name,
        "workspace_type": workspace.workspace_type,
        "description": workspace.description,
        "is_personal": workspace.is_personal,
        "is_archived": workspace.is_archived,
        "my_role": membership.role,
        "member_count": workspace_service.member_count(db, workspace.id),
        "project_count": workspace_service.project_count(db, workspace.id),
    }


def _detail(db: Session, workspace: Workspace, membership: WorkspaceMembership) -> dict:
    data = _summary(db, workspace, membership)
    data.update(
        {
            # A plain member should not be able to hand the join code around.
            "join_code": (
                workspace.join_code if workspace_service.is_oversight(membership) else None
            ),
            "default_project_visibility": workspace.default_project_visibility,
            "leads_can_assign_mentors": workspace.leads_can_assign_mentors,
            "created_at": workspace.created_at,
        }
    )
    return data


# --------------------------------------------------------------------------- #
# Workspace lifecycle
# --------------------------------------------------------------------------- #


@router.get("", response_model=list[WorkspaceSummary])
def my_workspaces(db: Session = Depends(get_db), user: User = Depends(current_user)):
    out = []
    for workspace in workspace_service.workspaces_for(db, user.id):
        membership = workspace_service.membership_for(db, workspace.id, user.id)
        out.append(_summary(db, workspace, membership))
    return out


@router.post("", response_model=WorkspaceDetail, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    workspace = workspace_service.create_workspace(
        db,
        creator=user,
        name=payload.name,
        organization_name=payload.organization_name,
        workspace_type=payload.workspace_type,
        description=payload.description,
        default_visibility=payload.default_project_visibility,
    )
    membership = workspace_service.membership_for(db, workspace.id, user.id)
    activity_service.record(
        db,
        project=None,
        actor=user,
        action="workspace_created",
        summary=f"{user.name} created {workspace.name}",
        kind=ActivityKind.MILESTONE,
        workspace_id=workspace.id,
    )
    db.commit()
    db.refresh(workspace)
    return _detail(db, workspace, membership)


@router.post("/join", response_model=WorkspaceDetail)
def join_with_code(
    payload: JoinRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    try:
        workspace, membership = workspace_service.join_by_code(db, user, payload.join_code)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    activity_service.record(
        db,
        project=None,
        actor=user,
        action="member_joined",
        summary=f"{user.name} joined the workspace",
        kind=ActivityKind.MILESTONE,
        workspace_id=workspace.id,
    )
    db.commit()
    return _detail(db, workspace, membership)


@router.post("/invitations/accept", response_model=WorkspaceDetail)
def accept_invite(
    payload: AcceptInvitation,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    try:
        workspace, membership = workspace_service.accept_invitation(db, user, payload.token)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    db.commit()
    return _detail(db, workspace, membership)


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
def read_workspace(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(get_membership),
):
    return _detail(db, workspace, membership)


@router.patch("/{workspace_id}", response_model=WorkspaceDetail)
def update_workspace(
    payload: WorkspaceUpdate,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(require_owner),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(workspace, field, value)
    db.commit()
    db.refresh(workspace)
    return _detail(db, workspace, membership)


@router.post("/{workspace_id}/archive", response_model=WorkspaceDetail)
def archive_workspace(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(require_owner),
):
    from app.models.project import utcnow

    workspace.archived_at = utcnow()
    db.commit()
    db.refresh(workspace)
    return _detail(db, workspace, membership)


# --------------------------------------------------------------------------- #
# Members and invitations
# --------------------------------------------------------------------------- #


@router.get("/{workspace_id}/members", response_model=list[MemberOut])
def list_members(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(get_membership),
):
    rows = db.scalars(
        select(WorkspaceMembership)
        .where(WorkspaceMembership.workspace_id == workspace.id)
        .order_by(WorkspaceMembership.role, WorkspaceMembership.id)
    ).all()
    projects = list(
        db.scalars(select(Project).where(Project.workspace_id == workspace.id))
    )
    out = []
    for row in rows:
        person = db.get(User, row.user_id)
        if person is None:
            continue
        owned = [p for p in projects if p.owner_id == person.id]
        last = max((p.last_activity for p in owned), default=None)
        out.append(
            MemberOut(
                user_id=person.id,
                name=person.name,
                email=person.email,
                role=row.role,
                joined_at=row.joined_at,
                project_count=len(owned),
                mentoring_count=sum(1 for p in projects if p.mentor_id == person.id),
                last_activity=last.date() if last else None,
            )
        )
    return out


@router.patch("/{workspace_id}/members/{user_id}", response_model=MemberOut)
def change_member_role(
    user_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(require_owner),
    actor: User = Depends(current_user),
):
    try:
        updated = workspace_service.change_role(db, workspace.id, user_id, payload.role)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    person = db.get(User, user_id)
    activity_service.record(
        db,
        project=None,
        actor=actor,
        action="role_changed",
        summary=f"{person.name if person else 'A member'} is now {payload.role.value}",
        kind=ActivityKind.PROJECT_CHANGE,
        workspace_id=workspace.id,
    )
    db.commit()
    projects = list(db.scalars(select(Project).where(Project.workspace_id == workspace.id)))
    owned = [p for p in projects if p.owner_id == user_id]
    last = max((p.last_activity for p in owned), default=None)
    return MemberOut(
        user_id=person.id,
        name=person.name,
        email=person.email,
        role=updated.role,
        joined_at=updated.joined_at,
        project_count=len(owned),
        mentoring_count=sum(1 for p in projects if p.mentor_id == user_id),
        last_activity=last.date() if last else None,
    )


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    user_id: int,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(require_owner),
):
    try:
        workspace_service.remove_member(db, workspace.id, user_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.commit()


@router.post(
    "/{workspace_id}/invitations",
    response_model=InvitationOut,
    status_code=status.HTTP_201_CREATED,
)
def invite(
    payload: InvitationCreate,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(require_owner),
    actor: User = Depends(current_user),
):
    invitation = workspace_service.create_invitation(
        db,
        workspace=workspace,
        created_by=actor,
        email=str(payload.email) if payload.email else None,
        role=payload.role,
    )
    db.commit()
    db.refresh(invitation)
    return invitation


@router.get("/{workspace_id}/invitations", response_model=list[InvitationOut])
def list_invitations(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(require_owner),
):
    from app.models.workspace_org import WorkspaceInvitation

    return list(
        db.scalars(
            select(WorkspaceInvitation)
            .where(WorkspaceInvitation.workspace_id == workspace.id)
            .order_by(WorkspaceInvitation.created_at.desc())
        )
    )


# --------------------------------------------------------------------------- #
# Overview
# --------------------------------------------------------------------------- #


@router.get("/{workspace_id}/projects", response_model=list[WorkspaceProjectRow])
def workspace_projects(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(get_membership),
    stage: str | None = Query(default=None),
    project_status: ProjectStatus | None = Query(default=None),
    mentor_id: int | None = Query(default=None),
    category: str | None = Query(default=None),
    competition: str | None = Query(default=None),
    approval: str | None = Query(default=None),
    search: str | None = Query(default=None),
):
    rows = workspace_analytics.rows_for(db, workspace, membership)
    if stage:
        rows = [r for r in rows if r.stage == stage]
    if project_status:
        rows = [r for r in rows if r.status == project_status]
    if mentor_id is not None:
        rows = [r for r in rows if r.mentor_id == mentor_id]
    if category:
        rows = [r for r in rows if r.category == category]
    if competition:
        rows = [r for r in rows if (r.competition_name or "") == competition]
    if approval:
        rows = [r for r in rows if r.approval_status == approval]
    if search:
        needle = search.lower()
        rows = [
            r
            for r in rows
            if needle in r.title.lower()
            or needle in r.owner_name.lower()
            or needle in r.current_question.lower()
        ]
    return rows


@router.get("/{workspace_id}/dashboard", response_model=WorkspaceDashboard)
def dashboard(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(get_membership),
):
    rows = workspace_analytics.rows_for(db, workspace, membership)
    visible_ids = [r.project_id for r in rows]
    today = date.today()

    deadlines = sorted(
        (
            {
                "project_id": r.project_id,
                "title": r.title,
                "owner_name": r.owner_name,
                "label": r.next_task or "Next milestone",
                "due": r.next_deadline,
                "days_away": (r.next_deadline - today).days,
            }
            for r in rows
            if r.next_deadline is not None
        ),
        key=lambda d: d["due"],
    )[:8]

    return {
        "workspace": _detail(db, workspace, membership),
        "stats": WorkspaceSummaryStats(**workspace_analytics.summary(rows)),
        "attention": (
            [AttentionGroup(**g) for g in workspace_analytics.attention_queue(rows)]
            if workspace_service.is_oversight(membership)
            else []
        ),
        "upcoming_deadlines": deadlines,
        "mentors": workspace_analytics.mentor_workload(db, workspace, rows),
        "competitions": sorted(
            {r.competition_name for r in rows if r.competition_name}
        ),
        "recent_activity": activity_service.feed(
            db,
            workspace.id,
            project_ids=None if workspace_service.is_oversight(membership) else visible_ids,
            limit=12,
        ),
    }


@router.get("/{workspace_id}/attention", response_model=list[AttentionGroup])
def attention(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(require_oversight),
):
    rows = workspace_analytics.rows_for(db, workspace, membership)
    return workspace_analytics.attention_queue(rows)


@router.get("/{workspace_id}/activity", response_model=list[ActivityOut])
def activity(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(get_membership),
    kind: ActivityKind | None = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    if workspace_service.is_oversight(membership):
        project_ids = None
    else:
        project_ids = [
            p.id for p in workspace_analytics.visible_projects(db, workspace, membership)
        ]
    return activity_service.feed(db, workspace.id, kind=kind, project_ids=project_ids, limit=limit)


@router.get("/{workspace_id}/projects/{project_id}/progress", response_model=StudentProgress)
def project_progress(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(get_membership),
    project: Project = Depends(get_project),
):
    if project.workspace_id != workspace.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    return workspace_analytics.student_progress(db, project)


@router.patch("/{workspace_id}/projects/{project_id}/mentor", response_model=WorkspaceProjectRow)
def assign_mentor(
    payload: MentorAssignment,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(get_membership),
    project: Project = Depends(get_project),
    actor: User = Depends(current_user),
):
    if project.workspace_id != workspace.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    if not workspace_service.can_assign_mentor(workspace, membership):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot assign mentors here.")

    if payload.mentor_id is not None:
        mentor_membership = workspace_service.membership_for(db, workspace.id, payload.mentor_id)
        if mentor_membership is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "That person is not in this workspace."
            )
        if mentor_membership.role == WorkspaceRole.MEMBER:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Give them the mentor role before assigning them projects.",
            )
    project.mentor_id = payload.mentor_id
    mentor = db.get(User, payload.mentor_id) if payload.mentor_id else None
    activity_service.record(
        db,
        project=project,
        actor=actor,
        action="mentor_assigned",
        summary=(
            f"{mentor.name} assigned as mentor on {project.title}"
            if mentor
            else f"Mentor removed from {project.title}"
        ),
    )
    db.commit()
    db.refresh(project)
    return workspace_analytics.build_row(db, project)


@router.patch(
    "/{workspace_id}/projects/{project_id}/visibility", response_model=WorkspaceProjectRow
)
def set_visibility(
    payload: VisibilityUpdate,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(get_membership),
    project: Project = Depends(get_project),
):
    if project.workspace_id != workspace.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    # The student decides how open their own work is; owners can override.
    if not (
        project.owner_id == membership.user_id or membership.role == WorkspaceRole.OWNER
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot change visibility here.")
    project.visibility = payload.visibility
    db.commit()
    db.refresh(project)
    return workspace_analytics.build_row(db, project)


@router.post(
    "/{workspace_id}/projects/{project_id}/comments",
    response_model=WorkspaceCommentOut,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    payload: WorkspaceCommentCreate,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(get_membership),
    project: Project = Depends(get_project),
    actor: User = Depends(current_user),
):
    if project.workspace_id != workspace.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    if not workspace_service.can_comment_on_project(project, membership):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot comment on this project.")

    comment = MentorComment(
        project_id=project.id,
        author_id=actor.id,
        author_name=actor.name,
        author_role=membership.role.value,
        section=payload.section,
        comment_type=payload.comment_type,
        body=payload.body,
        requires_action=payload.comment_type == CommentType.NEEDS_ACTION,
        resolved=payload.comment_type == CommentType.RESOLVED,
    )
    db.add(comment)
    activity_service.record(
        db,
        project=project,
        actor=actor,
        action="comment_added",
        summary=f"{actor.name} left feedback on {project.title}",
        kind=ActivityKind.COMMENT,
    )
    db.commit()
    db.refresh(comment)
    return comment


@router.get(
    "/{workspace_id}/projects/{project_id}/comments", response_model=list[WorkspaceCommentOut]
)
def list_comments(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMembership = Depends(get_membership),
    project: Project = Depends(get_project),
):
    if project.workspace_id != workspace.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    return list(
        db.scalars(
            select(MentorComment)
            .where(MentorComment.project_id == project.id)
            .order_by(MentorComment.created_at)
        )
    )
