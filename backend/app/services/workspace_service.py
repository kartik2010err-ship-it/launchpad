"""Workspace lifecycle and — more importantly — the permission predicates.

Every "can this person do this?" question in the app is answered here. Routes
call these; they never re-implement the rule. That way widening a permission is
a one-line change in one file rather than an audit of twenty route handlers.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import (
    OVERSIGHT_ROLES,
    WORKSPACE_ROLE_RANK,
    ProjectVisibility,
    WorkspaceRole,
    WorkspaceType,
)
from app.models.project import Project, User
from app.models.workspace_org import (
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
    generate_join_code,
)


# --------------------------------------------------------------------------- #
# Lookup
# --------------------------------------------------------------------------- #


def membership_for(db: Session, workspace_id: int, user_id: int) -> WorkspaceMembership | None:
    return db.scalars(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    ).first()


def workspaces_for(db: Session, user_id: int, include_archived: bool = False) -> list[Workspace]:
    stmt = (
        select(Workspace)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(WorkspaceMembership.user_id == user_id)
        .order_by(Workspace.is_personal.desc(), Workspace.name)
    )
    if not include_archived:
        stmt = stmt.where(Workspace.archived_at.is_(None))
    return list(db.scalars(stmt))


def member_count(db: Session, workspace_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(WorkspaceMembership)
            .where(WorkspaceMembership.workspace_id == workspace_id)
        )
        or 0
    )


def project_count(db: Session, workspace_id: int) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(Project).where(Project.workspace_id == workspace_id)
        )
        or 0
    )


# --------------------------------------------------------------------------- #
# Permission predicates — the whole authorization model, in one screen
# --------------------------------------------------------------------------- #


def has_rank(membership: WorkspaceMembership | None, minimum: WorkspaceRole) -> bool:
    if membership is None:
        return False
    return WORKSPACE_ROLE_RANK[membership.role] >= WORKSPACE_ROLE_RANK[minimum]


def is_oversight(membership: WorkspaceMembership | None) -> bool:
    """Owner or lead: may see every project in the workspace."""
    return membership is not None and membership.role in OVERSIGHT_ROLES


def can_view_project(project: Project, membership: WorkspaceMembership | None) -> bool:
    if membership is None or membership.workspace_id != project.workspace_id:
        return False
    if project.owner_id == membership.user_id:
        return True
    if is_oversight(membership):
        return True
    if project.mentor_id == membership.user_id:
        return True
    # Anything else depends on how open the project is.
    return project.visibility == ProjectVisibility.WORKSPACE


def can_edit_project(project: Project, membership: WorkspaceMembership | None) -> bool:
    """Editing the research itself stays with the student who is doing it.

    Owners and leads can oversee, comment and re-assign, but they do not get to
    rewrite a student's research question out from under them.
    """
    return membership is not None and project.owner_id == membership.user_id


def can_comment_on_project(project: Project, membership: WorkspaceMembership | None) -> bool:
    if membership is None or membership.workspace_id != project.workspace_id:
        return False
    if is_oversight(membership):
        return True
    if membership.role == WorkspaceRole.MENTOR and project.mentor_id == membership.user_id:
        return True
    # Students reply in their own thread.
    return project.owner_id == membership.user_id


def can_assign_mentor(workspace: Workspace, membership: WorkspaceMembership | None) -> bool:
    if membership is None:
        return False
    if membership.role == WorkspaceRole.OWNER:
        return True
    if membership.role == WorkspaceRole.LEAD:
        return workspace.leads_can_assign_mentors
    return False


def can_manage_members(membership: WorkspaceMembership | None) -> bool:
    """Inviting, removing and changing roles is owner-only."""
    return membership is not None and membership.role == WorkspaceRole.OWNER


def can_manage_settings(membership: WorkspaceMembership | None) -> bool:
    return membership is not None and membership.role == WorkspaceRole.OWNER


def can_view_all_projects(membership: WorkspaceMembership | None) -> bool:
    return is_oversight(membership)


# --------------------------------------------------------------------------- #
# Mutations
# --------------------------------------------------------------------------- #


def create_workspace(
    db: Session,
    *,
    creator: User,
    name: str,
    organization_name: str | None = None,
    workspace_type: WorkspaceType = WorkspaceType.RESEARCH_CLUB,
    description: str | None = None,
    is_personal: bool = False,
    default_visibility: ProjectVisibility = ProjectVisibility.PRIVATE,
) -> Workspace:
    """Create a workspace and make the creator its owner in one transaction."""

    code = generate_join_code(name)
    while db.scalars(select(Workspace).where(Workspace.join_code == code)).first():
        code = generate_join_code(name)

    workspace = Workspace(
        name=name.strip(),
        organization_name=(organization_name or None),
        workspace_type=workspace_type,
        description=description or None,
        join_code=code,
        is_personal=is_personal,
        default_project_visibility=default_visibility,
        created_by_id=creator.id,
    )
    db.add(workspace)
    db.flush()

    db.add(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=creator.id, role=WorkspaceRole.OWNER
        )
    )
    db.flush()
    return workspace


def ensure_personal_workspace(db: Session, user: User) -> Workspace:
    """Every account gets a private space, so the app is useful before any club."""

    existing = db.scalars(
        select(Workspace)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(WorkspaceMembership.user_id == user.id, Workspace.is_personal.is_(True))
    ).first()
    if existing:
        return existing
    return create_workspace(
        db,
        creator=user,
        name="My Research Projects",
        workspace_type=WorkspaceType.PERSONAL,
        description="Your own space. Nothing here is shared with a club.",
        is_personal=True,
    )


def resolve_target_workspace(db: Session, user: User, workspace_id: int | None) -> Workspace:
    """Where a new project should live.

    Explicit id wins (membership enforced). Otherwise fall back to the user's
    personal workspace, creating it if this is their first project — a lone
    student should never have to understand workspaces to get started.
    """

    if workspace_id is not None:
        workspace = db.get(Workspace, workspace_id)
        if workspace is None or membership_for(db, workspace.id, user.id) is None:
            raise LookupError("Workspace not found.")
        if workspace.is_archived:
            raise PermissionError("That workspace has been archived.")
        return workspace
    return ensure_personal_workspace(db, user)


def add_member(
    db: Session, workspace: Workspace, user: User, role: WorkspaceRole = WorkspaceRole.MEMBER
) -> WorkspaceMembership:
    existing = membership_for(db, workspace.id, user.id)
    if existing:
        return existing
    membership = WorkspaceMembership(workspace_id=workspace.id, user_id=user.id, role=role)
    db.add(membership)
    db.flush()
    return membership


def join_by_code(db: Session, user: User, code: str) -> tuple[Workspace, WorkspaceMembership]:
    workspace = db.scalars(
        select(Workspace).where(Workspace.join_code == code.strip().upper())
    ).first()
    if workspace is None:
        raise LookupError("No workspace matches that join code.")
    if workspace.is_archived:
        raise PermissionError("That workspace has been archived.")
    return workspace, add_member(db, workspace, user, WorkspaceRole.MEMBER)


def create_invitation(
    db: Session,
    *,
    workspace: Workspace,
    created_by: User,
    email: str | None,
    role: WorkspaceRole = WorkspaceRole.MEMBER,
) -> WorkspaceInvitation:
    invitation = WorkspaceInvitation(
        workspace_id=workspace.id,
        email=(email or None),
        role=role,
        token=WorkspaceInvitation.new_token(),
        expires_at=WorkspaceInvitation.default_expiry(),
        created_by_id=created_by.id,
    )
    db.add(invitation)
    db.flush()
    return invitation


def accept_invitation(
    db: Session, user: User, token: str
) -> tuple[Workspace, WorkspaceMembership]:
    invitation = db.scalars(
        select(WorkspaceInvitation).where(WorkspaceInvitation.token == token)
    ).first()
    if invitation is None:
        raise LookupError("That invitation link is not valid.")
    if not invitation.is_usable:
        raise PermissionError("That invitation has already been used or has expired.")

    workspace = db.get(Workspace, invitation.workspace_id)
    if workspace is None or workspace.is_archived:
        raise PermissionError("That workspace is no longer available.")

    membership = add_member(db, workspace, user, invitation.role)
    invitation.accepted_at = func.now()
    invitation.accepted_by_id = user.id
    db.flush()
    return workspace, membership


def change_role(
    db: Session, workspace_id: int, target_user_id: int, role: WorkspaceRole
) -> WorkspaceMembership:
    membership = membership_for(db, workspace_id, target_user_id)
    if membership is None:
        raise LookupError("That person is not in this workspace.")
    if membership.role == WorkspaceRole.OWNER and role != WorkspaceRole.OWNER:
        _guard_last_owner(db, workspace_id, membership.user_id)
    membership.role = role
    db.flush()
    return membership


def remove_member(db: Session, workspace_id: int, target_user_id: int) -> None:
    membership = membership_for(db, workspace_id, target_user_id)
    if membership is None:
        raise LookupError("That person is not in this workspace.")
    if membership.role == WorkspaceRole.OWNER:
        _guard_last_owner(db, workspace_id, target_user_id)
    # Their projects stay in the workspace; unassign them as a mentor so no
    # project points at someone who can no longer see it.
    for project in db.scalars(
        select(Project).where(
            Project.workspace_id == workspace_id, Project.mentor_id == target_user_id
        )
    ):
        project.mentor_id = None
    db.delete(membership)
    db.flush()


def _guard_last_owner(db: Session, workspace_id: int, user_id: int) -> None:
    owners = db.scalars(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.role == WorkspaceRole.OWNER,
        )
    ).all()
    if len(owners) <= 1 and any(o.user_id == user_id for o in owners):
        raise PermissionError(
            "This is the only owner. Promote someone else to owner first."
        )
