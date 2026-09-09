"""Aggregation for the workspace dashboard.

Everything here is read-only and scoped to one workspace and one viewer. The
viewer matters: a mentor asking for "the project table" must get only their
assigned projects, so scoping happens here rather than being trusted to the UI.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    ProjectStatus,
    Stage,
    TaskStatus,
    WorkspaceRole,
)
from app.models.project import Project, User
from app.models.team import Team
from app.models.workspace import Evaluation, MentorComment, PosterDraft, TimelineTask
from app.models.workspace_org import Workspace, WorkspaceMembership
from app.services import project_status_service as status_service
from app.services import team_service, workspace_service
from app.services.readiness import AREA_LABELS, compute as compute_readiness

# Progress areas surfaced in the compact per-student view.
PROGRESS_AREAS = ["research_question", "methodology", "experimentation", "analysis", "poster"]


@dataclass
class ProjectRow:
    """One line of the workspace project table."""

    project_id: int
    title: str
    # Null for a team project — ``owner_name`` carries the team name instead, so
    # one catalog can list individual and team work side by side.
    owner_id: int | None
    owner_name: str
    owner_kind: str
    team_id: int | None
    team_name: str | None
    member_names: list[str]
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
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    open_comments: int = 0


def _dimension(evaluation: Evaluation | None, key: str) -> int | None:
    if evaluation is None:
        return None
    for dim in evaluation.dimensions or []:
        if isinstance(dim, dict) and dim.get("key") == key:
            return dim.get("score")
    return None


def _task_percent(tasks: list[TimelineTask], phases: set[str]) -> int:
    relevant = [t for t in tasks if t.phase in phases]
    if not relevant:
        return 0
    done = sum(1 for t in relevant if t.status == TaskStatus.COMPLETE)
    return round(done / len(relevant) * 100)


def visible_projects(
    db: Session, workspace: Workspace, membership: WorkspaceMembership
) -> list[Project]:
    """The projects this viewer may open, in this workspace."""

    projects = list(
        db.scalars(
            select(Project)
            .where(Project.workspace_id == workspace.id)
            .order_by(Project.updated_at.desc())
        )
    )
    if workspace_service.is_oversight(membership):
        return projects
    return [p for p in projects if workspace_service.can_view_project(db, p, membership)]


def build_row(db: Session, project: Project, today: date | None = None) -> ProjectRow:
    today = today or date.today()
    verdict = status_service.compute(db, project, today)
    signals = verdict.signals

    evaluation = db.scalars(
        select(Evaluation)
        .where(Evaluation.project_id == project.id)
        .order_by(Evaluation.created_at.desc())
    ).first()

    tasks = list(db.scalars(select(TimelineTask).where(TimelineTask.project_id == project.id)))
    poster = db.scalars(select(PosterDraft).where(PosterDraft.project_id == project.id)).first()
    poster_sections = (poster.sections if poster else {}) or {}
    filled = sum(1 for v in poster_sections.values() if isinstance(v, str) and v.strip())
    poster_percent = (
        min(100, round(filled / 8 * 100)) if filled else _task_percent(tasks, {"poster"})
    )

    team = db.get(Team, project.owner_team_id) if project.owner_team_id else None
    if team is not None:
        members = team_service.members_of(db, team.id)
        member_names = [m.name for m in members]
        owner_label = team.name
    else:
        owner = db.get(User, project.owner_id) if project.owner_id else None
        member_names = [owner.name] if owner else []
        owner_label = owner.name if owner else "Unknown"

    mentor_id = project.mentor_id or (team.mentor_id if team else None)
    mentor = db.get(User, mentor_id) if mentor_id else None

    safety_flags: list[str] = []
    if evaluation:
        for flag in (evaluation.safety or {}).get("flags", []) or []:
            if isinstance(flag, dict) and flag.get("label"):
                safety_flags.append(flag["label"])

    # Mirrors project_status_service: flags only mean "paperwork outstanding"
    # while the project is still at or before the approval stage.
    if project.stage == Stage.COMPLETE:
        approval = "complete"
    elif signals.awaiting_approval:
        approval = "required"
    elif project.stage in {Stage.IDEA, Stage.QUESTION_REFINEMENT}:
        approval = "not_started"
    else:
        approval = "cleared"

    novelty = None
    if evaluation and evaluation.novelty:
        novelty = (evaluation.novelty or {}).get("status")

    last = status_service._as_aware(project.last_activity_at)

    return ProjectRow(
        project_id=project.id,
        title=project.title,
        owner_id=project.owner_id,
        owner_name=owner_label,
        owner_kind=str(project.owner_kind),
        team_id=team.id if team else None,
        team_name=team.name if team else None,
        member_names=member_names,
        category=str(project.category),
        project_type=str(project.project_type),
        stage=str(project.stage),
        current_question=project.current_question,
        competition_name=project.competition_name,
        competition_date=project.competition_date,
        days_to_competition=signals.days_to_deadline,
        readiness=signals.readiness,
        research_question_score=_dimension(evaluation, "research_question"),
        methodology_score=_dimension(evaluation, "methodology"),
        feasibility_score=_dimension(evaluation, "feasibility"),
        novelty_status=novelty,
        approval_status=approval,
        safety_flags=safety_flags,
        experimentation_percent=_task_percent(tasks, {"experimentation"}),
        poster_percent=poster_percent,
        interview_percent=_task_percent(tasks, {"interview_preparation"}),
        methodology_percent=_task_percent(tasks, {"experimental_design"}),
        next_deadline=signals.next_deadline,
        next_task=signals.next_task_title,
        last_activity=last.date() if last else None,
        days_inactive=signals.days_inactive,
        mentor_id=project.mentor_id,
        mentor_name=mentor.name if mentor else None,
        status=verdict.status,
        reasons=verdict.reasons,
        blockers=verdict.blockers,
        open_comments=signals.open_action_comments,
    )


def rows_for(
    db: Session, workspace: Workspace, membership: WorkspaceMembership
) -> list[ProjectRow]:
    return [build_row(db, p) for p in visible_projects(db, workspace, membership)]


def summary(rows: list[ProjectRow]) -> dict:
    readiness_values = [r.readiness for r in rows if r.readiness is not None]
    by_status = Counter(str(r.status) for r in rows)
    return {
        "total_projects": len(rows),
        "active_projects": sum(1 for r in rows if r.status != ProjectStatus.COMPLETE),
        "on_track": by_status.get(str(ProjectStatus.ON_TRACK), 0),
        "needs_attention": by_status.get(str(ProjectStatus.NEEDS_ATTENTION), 0),
        "at_risk": by_status.get(str(ProjectStatus.AT_RISK), 0),
        "blocked": by_status.get(str(ProjectStatus.BLOCKED), 0),
        "complete": by_status.get(str(ProjectStatus.COMPLETE), 0),
        "awaiting_approval": sum(1 for r in rows if r.approval_status == "required"),
        "needing_mentor_review": sum(1 for r in rows if r.open_comments > 0),
        "without_mentor": sum(1 for r in rows if r.mentor_id is None),
        "near_deadline": sum(
            1
            for r in rows
            if r.days_to_competition is not None and 0 <= r.days_to_competition <= 14
        ),
        "average_readiness": (
            round(sum(readiness_values) / len(readiness_values)) if readiness_values else None
        ),
        "by_stage": dict(Counter(r.stage for r in rows)),
        "by_category": dict(Counter(r.category for r in rows)),
        "average_poster": (
            round(sum(r.poster_percent for r in rows) / len(rows)) if rows else 0
        ),
        "average_interview": (
            round(sum(r.interview_percent for r in rows) / len(rows)) if rows else 0
        ),
    }


def attention_queue(rows: list[ProjectRow]) -> list[dict]:
    """The "who needs help today" list, grouped so it reads as sentences."""

    groups: list[dict] = []

    def add(key: str, severity: str, label: str, matched: list[ProjectRow]) -> None:
        if matched:
            groups.append(
                {
                    "key": key,
                    "severity": severity,
                    "label": label.format(n=len(matched)),
                    "projects": [
                        {
                            "project_id": r.project_id,
                            "title": r.title,
                            "owner_name": r.owner_name,
                            "detail": (r.blockers + r.reasons or ["—"])[0],
                        }
                        for r in matched
                    ],
                }
            )

    add(
        "blocked",
        "high",
        "{n} project(s) are blocked",
        [r for r in rows if r.status == ProjectStatus.BLOCKED],
    )
    add(
        "safety",
        "high",
        "{n} project(s) have unresolved rules or safety flags",
        [r for r in rows if r.safety_flags and r.approval_status == "required"],
    )
    add(
        "at_risk",
        "high",
        "{n} project(s) are behind schedule",
        [r for r in rows if r.status == ProjectStatus.AT_RISK],
    )
    add(
        "deadline",
        "medium",
        "{n} competition deadline(s) within 14 days",
        [
            r
            for r in rows
            if r.days_to_competition is not None and 0 <= r.days_to_competition <= 14
        ],
    )
    add(
        "mentor_review",
        "medium",
        "{n} project(s) are waiting on mentor feedback",
        [r for r in rows if r.open_comments > 0],
    )
    add(
        "inactive",
        "medium",
        "{n} student(s) have been quiet for over %d days" % status_service.INACTIVE_DAYS,
        [r for r in rows if r.days_inactive >= status_service.INACTIVE_DAYS],
    )
    add(
        "unassigned",
        "low",
        "{n} project(s) have no mentor assigned",
        [r for r in rows if r.mentor_id is None],
    )
    return groups


def mentor_workload(db: Session, workspace: Workspace, rows: list[ProjectRow]) -> list[dict]:
    mentors = list(
        db.scalars(
            select(User)
            .join(WorkspaceMembership, WorkspaceMembership.user_id == User.id)
            .where(
                WorkspaceMembership.workspace_id == workspace.id,
                WorkspaceMembership.role.in_(
                    [WorkspaceRole.MENTOR, WorkspaceRole.LEAD, WorkspaceRole.OWNER]
                ),
            )
            .order_by(User.name)
        )
    )
    out = []
    for mentor in mentors:
        assigned = [r for r in rows if r.mentor_id == mentor.id]
        out.append(
            {
                "user_id": mentor.id,
                "name": mentor.name,
                "email": mentor.email,
                "assigned_projects": len(assigned),
                "needing_review": sum(1 for r in assigned if r.open_comments > 0),
                "at_risk": sum(
                    1
                    for r in assigned
                    if r.status in {ProjectStatus.AT_RISK, ProjectStatus.BLOCKED}
                ),
            }
        )
    return out


def student_progress(db: Session, project: Project) -> dict:
    """The compact per-student breakdown: area percentages plus what is next."""

    readiness = compute_readiness(db, project)
    areas = [
        {"key": a.key, "label": a.label, "percent": a.percent, "note": a.note}
        for a in readiness.areas
    ]
    row = build_row(db, project)
    return {
        "areas": areas,
        "overall": readiness.overall,
        "current_priority": row.next_task,
        "next_deadline": row.next_deadline,
        "days_to_next_deadline": (
            (row.next_deadline - date.today()).days if row.next_deadline else None
        ),
        "current_risk": (row.blockers + row.reasons or [None])[0],
        "status": row.status,
    }


__all__ = [
    "ProjectRow",
    "AREA_LABELS",
    "attention_queue",
    "build_row",
    "mentor_workload",
    "rows_for",
    "student_progress",
    "summary",
    "visible_projects",
]
