"""Team lifecycle and the membership lookups authorization is built on.

Two rules drive everything in this file:

1. A team join code adds a person to a team. It never creates a project. The
   team's project is one row that every member already shares.
2. A team lives inside a workspace. You cannot be on a team without being in its
   workspace, so workspace authorization keeps working unchanged underneath.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import TeamRole, WorkspaceRole
from app.models.project import Project, User, utcnow
from app.models.team import Team, TeamContribution, TeamMembership, generate_team_code
from app.models.workspace_org import Workspace
from app.services import competitions, workspace_service


# --------------------------------------------------------------------------- #
# Lookup
# --------------------------------------------------------------------------- #


def get_team(db: Session, team_id: int) -> Team | None:
    return db.get(Team, team_id)


def teams_in_workspace(db: Session, workspace_id: int, include_archived: bool = False) -> list[Team]:
    stmt = select(Team).where(Team.workspace_id == workspace_id).order_by(Team.name)
    if not include_archived:
        stmt = stmt.where(Team.archived_at.is_(None))
    return list(db.scalars(stmt))


def team_membership_for(db: Session, team_id: int, user_id: int) -> TeamMembership | None:
    return db.scalars(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id, TeamMembership.user_id == user_id
        )
    ).first()


def memberships_of(db: Session, team_id: int) -> list[TeamMembership]:
    return list(
        db.scalars(
            select(TeamMembership)
            .where(TeamMembership.team_id == team_id)
            .order_by(TeamMembership.role, TeamMembership.id)
        )
    )


def member_ids(db: Session, team_id: int) -> set[int]:
    return set(
        db.scalars(select(TeamMembership.user_id).where(TeamMembership.team_id == team_id))
    )


def members_of(db: Session, team_id: int) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .join(TeamMembership, TeamMembership.user_id == User.id)
            .where(TeamMembership.team_id == team_id)
            .order_by(User.name)
        )
    )


def member_count(db: Session, team_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(TeamMembership)
            .where(TeamMembership.team_id == team_id)
        )
        or 0
    )


def teams_for_user(db: Session, workspace_id: int, user_id: int) -> list[Team]:
    return list(
        db.scalars(
            select(Team)
            .join(TeamMembership, TeamMembership.team_id == Team.id)
            .where(
                Team.workspace_id == workspace_id,
                TeamMembership.user_id == user_id,
                Team.archived_at.is_(None),
            )
            .order_by(Team.name)
        )
    )


def project_for_team(db: Session, team_id: int) -> Project | None:
    """The team's single shared project. There is at most one, by design."""

    return db.scalars(select(Project).where(Project.owner_team_id == team_id)).first()


def is_team_member(db: Session, team_id: int, user_id: int) -> bool:
    return team_membership_for(db, team_id, user_id) is not None


# --------------------------------------------------------------------------- #
# Team-size rules (competition-configurable, never claimed as compliance)
# --------------------------------------------------------------------------- #


def resolved_max_size(db: Session, team: Team) -> int:
    """How many people this team may hold.

    Competition configuration is the baseline; an explicit per-team override
    wins, because a coach with a documented exception should not have to edit
    the registry.
    """

    if team.max_members_override is not None:
        return team.max_members_override
    return competitions.team_rules(team.competition_key).max_team_size


def size_check(db: Session, team: Team) -> dict:
    """Everything the UI needs to explain the limit without restating the rule."""

    rules = competitions.team_rules(team.competition_key)
    limit = resolved_max_size(db, team)
    count = member_count(db, team.id)
    return {
        "member_count": count,
        "max_team_size": limit,
        "seats_left": max(0, limit - count),
        "is_full": count >= limit,
        "limit_source": (
            "team_override" if team.max_members_override is not None else "competition_config"
        ),
        "membership_locked": team.is_locked,
        "rules": competitions.team_rules_payload(team.competition_key),
        "notice": rules.notice,
    }


def _guard_capacity(db: Session, team: Team) -> None:
    if team.is_archived:
        raise PermissionError("That team has been archived.")
    if team.is_locked:
        raise PermissionError(
            "This team's roster is locked. A workspace lead can unlock it if the "
            "competition still allows roster changes."
        )
    limit = resolved_max_size(db, team)
    if member_count(db, team.id) >= limit:
        raise PermissionError(
            f"{team.name} already has {limit} member(s), the maximum configured for "
            f"{competitions.get(team.competition_key or 'custom').name} in Research Coach."
        )


# --------------------------------------------------------------------------- #
# Permission predicates
# --------------------------------------------------------------------------- #


def can_manage_teams(membership) -> bool:
    """Creating, archiving, assigning mentors: workspace owners and leads."""

    return workspace_service.is_oversight(membership)


def can_edit_team_settings(db: Session, team: Team, membership) -> bool:
    if membership is None or membership.workspace_id != team.workspace_id:
        return False
    if workspace_service.is_oversight(membership):
        return True
    team_membership = team_membership_for(db, team.id, membership.user_id)
    return team_membership is not None and team_membership.role == TeamRole.TEAM_LEAD


def can_view_team(db: Session, team: Team, membership) -> bool:
    """Anyone in the workspace can see that a team exists and who is on it.

    The team's *project* is a separate question, answered by
    ``workspace_service.can_view_project``.
    """

    return membership is not None and membership.workspace_id == team.workspace_id


def can_log_contribution(db: Session, team: Team, membership, target_user_id: int) -> bool:
    """Members log their own work; mentors and leads may log or request anyone's."""

    if membership is None or membership.workspace_id != team.workspace_id:
        return False
    if workspace_service.is_oversight(membership) or team.mentor_id == membership.user_id:
        return True
    return (
        target_user_id == membership.user_id
        and is_team_member(db, team.id, membership.user_id)
    )


# --------------------------------------------------------------------------- #
# Mutations
# --------------------------------------------------------------------------- #


def create_team(
    db: Session,
    *,
    workspace: Workspace,
    creator: User,
    name: str,
    description: str | None = None,
    mentor_id: int | None = None,
    competition_key: str | None = None,
    max_members_override: int | None = None,
    is_discoverable: bool = True,
) -> Team:
    name = name.strip()
    if not name:
        raise ValueError("A team needs a name.")
    existing = db.scalars(
        select(Team).where(Team.workspace_id == workspace.id, func.lower(Team.name) == name.lower())
    ).first()
    if existing is not None:
        raise ValueError(f"This workspace already has a team called {name}.")

    code = generate_team_code(name)
    while db.scalars(select(Team).where(Team.join_code == code)).first():
        code = generate_team_code(name)

    team = Team(
        workspace_id=workspace.id,
        name=name,
        description=description or None,
        join_code=code,
        mentor_id=mentor_id,
        competition_key=competition_key,
        max_members_override=max_members_override,
        is_discoverable=is_discoverable,
        created_by_id=creator.id,
    )
    db.add(team)
    db.flush()
    return team


def add_team_member(
    db: Session, team: Team, user: User, role: TeamRole = TeamRole.MEMBER
) -> TeamMembership:
    """Put someone on a team. Idempotent, and never creates a project.

    Requires that they are already in the workspace: a team code is a second
    door inside a building you have already entered.
    """

    existing = team_membership_for(db, team.id, user.id)
    if existing is not None:
        return existing
    if workspace_service.membership_for(db, team.workspace_id, user.id) is None:
        raise PermissionError(
            "Join the workspace first — a team code only works once you are in the workspace."
        )
    _guard_capacity(db, team)
    membership = TeamMembership(team_id=team.id, user_id=user.id, role=role)
    db.add(membership)
    db.flush()
    return membership


def join_by_code(
    db: Session, user: User, code: str, *, workspace_id: int | None = None
) -> tuple[Team, TeamMembership]:
    """Team join codes are a separate namespace from workspace join codes.

    A workspace code here is a miss, not a fallback — silently joining the wrong
    kind of thing would be worse than an error message.

    ``workspace_id`` scopes the lookup. A code that is valid in a workspace the
    caller is not in must be indistinguishable from a code that does not exist,
    so the scope is checked before anything else can raise a different error.
    """

    team = db.scalars(select(Team).where(Team.join_code == code.strip().upper())).first()
    not_found = LookupError(
        "No team in this workspace matches that code."
        if workspace_id is not None
        else "No team matches that code."
    )
    if team is None:
        raise not_found
    if workspace_id is not None and team.workspace_id != workspace_id:
        raise not_found
    if team.is_archived:
        raise PermissionError("That team has been archived.")
    return team, add_team_member(db, team, user)


def remove_team_member(db: Session, team: Team, user_id: int) -> None:
    membership = team_membership_for(db, team.id, user_id)
    if membership is None:
        raise LookupError("That person is not on this team.")
    db.delete(membership)
    db.flush()


def set_member_role(db: Session, team: Team, user_id: int, role: TeamRole) -> TeamMembership:
    membership = team_membership_for(db, team.id, user_id)
    if membership is None:
        raise LookupError("That person is not on this team.")
    membership.role = role
    db.flush()
    return membership


def assign_mentor(db: Session, team: Team, mentor_id: int | None) -> Team:
    """Assign the team mentor, and keep the shared project's mentor in step."""

    if mentor_id is not None:
        mentor_membership = workspace_service.membership_for(db, team.workspace_id, mentor_id)
        if mentor_membership is None:
            raise LookupError("That person is not in this workspace.")
        if mentor_membership.role == WorkspaceRole.MEMBER:
            raise PermissionError("Give them the mentor role before assigning them a team.")
    team.mentor_id = mentor_id
    project = project_for_team(db, team.id)
    if project is not None:
        project.mentor_id = mentor_id
    db.flush()
    return team


def set_membership_lock(db: Session, team: Team, locked: bool) -> Team:
    team.membership_locked_at = utcnow() if locked else None
    db.flush()
    return team


def archive_team(db: Session, team: Team) -> Team:
    team.archived_at = utcnow()
    db.flush()
    return team


def contributions_for_project(db: Session, project_id: int) -> list[TeamContribution]:
    return list(
        db.scalars(
            select(TeamContribution)
            .where(TeamContribution.project_id == project_id)
            .order_by(TeamContribution.contribution_date.desc(), TeamContribution.id.desc())
        )
    )


def contribution_summary(db: Session, project_id: int) -> list[dict]:
    """Per-member rollup: what each person has taken on and finished."""

    rows = contributions_for_project(db, project_id)
    by_user: dict[int, dict] = {}
    for row in rows:
        bucket = by_user.setdefault(
            row.user_id,
            {"user_id": row.user_id, "name": "", "tasks": 0, "completed": 0, "hours": 0.0},
        )
        bucket["tasks"] += 1
        bucket["completed"] += 1 if row.completed else 0
        bucket["hours"] += row.hours or 0.0
    for user_id, bucket in by_user.items():
        person = db.get(User, user_id)
        bucket["name"] = person.name if person else "Unknown"
        bucket["hours"] = round(bucket["hours"], 1)
    return sorted(by_user.values(), key=lambda b: b["name"])
