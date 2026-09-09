"""Append-only activity log.

Called from routes at the moment something meaningful happens. Kept tiny and
side-effect-only so a failure to log can never break the action being logged.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ActivityKind
from app.models.project import Project, User
from app.models.project import utcnow
from app.models.workspace_org import ProjectActivity


def record(
    db: Session,
    *,
    project: Project | None,
    actor: User | None,
    action: str,
    summary: str,
    kind: ActivityKind = ActivityKind.PROJECT_CHANGE,
    workspace_id: int | None = None,
) -> ProjectActivity:
    entry = ProjectActivity(
        workspace_id=workspace_id or (project.workspace_id if project else 0),
        project_id=project.id if project else None,
        project_title=project.title if project else None,
        user_id=actor.id if actor else None,
        actor_name=actor.name if actor else "System",
        kind=kind.value,
        action=action,
        summary=summary,
    )
    db.add(entry)
    if project is not None:
        # Any logged action counts as the student being alive on this project.
        project.last_activity_at = utcnow()
    db.flush()
    return entry


def feed(
    db: Session,
    workspace_id: int,
    *,
    kind: ActivityKind | None = None,
    project_ids: list[int] | None = None,
    limit: int = 50,
) -> list[ProjectActivity]:
    stmt = (
        select(ProjectActivity)
        .where(ProjectActivity.workspace_id == workspace_id)
        .order_by(ProjectActivity.created_at.desc(), ProjectActivity.id.desc())
        .limit(limit)
    )
    if kind is not None:
        stmt = stmt.where(ProjectActivity.kind == kind.value)
    if project_ids is not None:
        # Mentors and members only see the feed for projects they may open.
        if not project_ids:
            return []
        stmt = stmt.where(ProjectActivity.project_id.in_(project_ids))
    return list(db.scalars(stmt))
