"""Shared router dependencies.

Authorization funnels through here. ``get_project`` is the important one: every
existing research route (question, timeline, rubric, poster, judging, notebook)
already depends on it, so making it workspace-aware secured all of them at once
without touching those handlers.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.core.security import read_token
from app.db.session import get_db
from app.models.enums import WorkspaceRole
from app.models.project import Project, User
from app.models.workspace_org import Workspace, WorkspaceMembership
from app.services import workspace_service


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    user_id = read_token(authorization.split(" ", 1)[1])
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session expired. Sign in again.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found.")
    return user


# --------------------------------------------------------------------------- #
# Workspace scope
# --------------------------------------------------------------------------- #


def get_workspace(
    workspace_id: int = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found.")
    if workspace_service.membership_for(db, workspace.id, user.id) is None:
        # Deliberately 404, not 403: a non-member should not be able to probe
        # which workspace ids exist.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found.")
    return workspace


def get_membership(
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> WorkspaceMembership:
    membership = workspace_service.membership_for(db, workspace.id, user.id)
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found.")
    return membership


def require_oversight(
    membership: WorkspaceMembership = Depends(get_membership),
) -> WorkspaceMembership:
    """Owner or lead."""
    if not workspace_service.is_oversight(membership):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only workspace owners and leads can do that."
        )
    return membership


def require_owner(
    membership: WorkspaceMembership = Depends(get_membership),
) -> WorkspaceMembership:
    if membership.role != WorkspaceRole.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the workspace owner can do that.")
    return membership


# --------------------------------------------------------------------------- #
# Project scope
# --------------------------------------------------------------------------- #


def _membership_or_404(db: Session, project: Project, user: User) -> WorkspaceMembership:
    membership = workspace_service.membership_for(db, project.workspace_id, user.id)
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    return membership


def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Project:
    """Read access: owner, assigned mentor, workspace owner/lead, or — when the
    project is set to workspace visibility — any member."""

    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    membership = _membership_or_404(db, project, user)
    if not workspace_service.can_view_project(project, membership):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot open this project.")
    return project


def get_editable_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Project:
    """Write access to the research itself: the student who owns it, only.

    Leads oversee and comment; they do not rewrite a student's work.
    """

    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    membership = _membership_or_404(db, project, user)
    if not workspace_service.can_view_project(project, membership):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot open this project.")
    if not workspace_service.can_edit_project(project, membership):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the student who owns this project can change its research.",
        )
    return project


def project_membership(
    project: Project = Depends(get_project),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> WorkspaceMembership:
    return _membership_or_404(db, project, user)
