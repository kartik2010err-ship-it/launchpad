"""The logged-in Home dashboard (section 34).

Four questions, in this order, and nothing else:

    What am I working on?   What should I do next?
    What needs attention?   What is coming up?

The discipline here is subtraction. A student who opens this page and sees
twelve cards learns nothing; the whole value is that one action is bigger than
everything around it. Anything that does not answer one of those four questions
belongs on another screen.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.enums import OutreachStatus, TaskStatus
from app.models.historical import HistoricalProject
from app.models.outreach import OutreachContact
from app.models.project import Project, User
from app.models.team import TeamMembership
from app.models.workspace import TimelineTask
from app.services import (
    assistant_context,
    guide_recommender,
    historical_service,
    next_action,
    workspace_service,
)

SOON_DAYS = 14


def _visible_projects(db: Session, user: User) -> list[Project]:
    """Projects this person is actually doing — owned, or on their team.

    Deliberately not every project they can *see*. A workspace owner's home
    should show their own work; oversight lives on the workspace dashboard.
    """

    team_ids = [
        row.team_id
        for row in db.scalars(
            select(TeamMembership).where(TeamMembership.user_id == user.id)
        ).all()
    ]
    stmt = select(Project).where(
        or_(
            Project.owner_id == user.id,
            Project.owner_team_id.in_(team_ids) if team_ids else False,
        )
    )
    return list(db.scalars(stmt.order_by(Project.last_activity_at.desc())).all())


def build(db: Session, user: User, today: date | None = None) -> dict:
    today = today or date.today()
    projects = _visible_projects(db, user)
    active = projects[0] if projects else None

    if active is None:
        return {
            "has_project": False,
            "project": None,
            "next_action": next_action.compute(None),
            "attention": [],
            "upcoming": [],
            "suggested_guides": [],
            "similar_historical_count": 0,
            "other_projects": [],
            "follow_ups_due": 0,
        }

    context = assistant_context.build(db, active)
    evaluation = context.get("evaluation") or {}

    # ---- what needs attention ------------------------------------------- #
    attention: list[dict] = []
    for flag in evaluation.get("safety_flags") or []:
        attention.append({"kind": "safety", "label": flag, "detail": "Approval may be required."})

    overdue = db.scalars(
        select(TimelineTask)
        .where(TimelineTask.project_id == active.id)
        .where(TimelineTask.status != TaskStatus.COMPLETE)
        .where(TimelineTask.due_date.is_not(None))
        .where(TimelineTask.due_date < today)
        .order_by(TimelineTask.due_date)
    ).all()
    for task in overdue[:3]:
        attention.append(
            {
                "kind": "overdue",
                "label": task.title,
                "detail": f"Was due {task.due_date.isoformat()}.",
            }
        )

    blocked = db.scalars(
        select(TimelineTask)
        .where(TimelineTask.project_id == active.id)
        .where(TimelineTask.status == TaskStatus.BLOCKED)
    ).all()
    for task in blocked[:2]:
        attention.append({"kind": "blocked", "label": task.title, "detail": "Marked blocked."})

    follow_ups = db.scalars(
        select(OutreachContact)
        .where(OutreachContact.user_id == user.id)
        .where(OutreachContact.status == OutreachStatus.SENT)
        .where(OutreachContact.follow_up_done.is_(False))
        .where(OutreachContact.follow_up_on.is_not(None))
        .where(OutreachContact.follow_up_on <= today)
    ).all()
    if follow_ups:
        attention.append(
            {
                "kind": "outreach",
                "label": f"{len(follow_ups)} outreach follow-up{'s' if len(follow_ups) > 1 else ''} due",
                "detail": "Send one follow-up, not three.",
            }
        )

    # ---- what is coming up ------------------------------------------------ #
    horizon = today + timedelta(days=SOON_DAYS)
    upcoming = [
        {
            "title": task.title,
            "due_date": task.due_date.isoformat(),
            "phase": str(task.phase),
            "days_away": (task.due_date - today).days,
        }
        for task in db.scalars(
            select(TimelineTask)
            .where(TimelineTask.project_id == active.id)
            .where(TimelineTask.status != TaskStatus.COMPLETE)
            .where(TimelineTask.due_date.is_not(None))
            .where(TimelineTask.due_date >= today)
            .where(TimelineTask.due_date <= horizon)
            .order_by(TimelineTask.due_date)
            .limit(4)
        ).all()
    ]
    if active.competition_date and today <= active.competition_date <= horizon + timedelta(days=60):
        upcoming.append(
            {
                "title": active.competition_name or "Competition",
                "due_date": active.competition_date.isoformat(),
                "phase": "competition",
                "days_away": (active.competition_date - today).days,
            }
        )

    # ---- what to read, and what to compare against ------------------------ #
    guides = guide_recommender.for_evaluation(
        evaluation.get("dimensions") and [] or [], stage=str(active.stage), limit=2
    )
    if not guides:
        guides = guide_recommender.for_stage(str(active.stage))[:2]

    # Only counted, never fabricated: an empty catalogue reports zero.
    catalogue_size = db.scalar(select(HistoricalProject.id).limit(1))
    similar_count = 0
    if catalogue_size is not None:
        similar_count = len(historical_service.similar_to_project(db, active, limit=5)["matches"])

    return {
        "has_project": True,
        "project": {
            "id": active.id,
            "title": active.title,
            "question": active.current_question,
            "stage": str(active.stage),
            "status": str(active.status),
            "readiness": evaluation.get("overall_score"),
            "information_completeness": context.get("information_completeness"),
            "competition": active.competition_name,
            "competition_date": active.competition_date.isoformat()
            if active.competition_date
            else None,
            "is_team_project": active.owner_team_id is not None,
            "workspace_id": active.workspace_id,
        },
        "next_action": next_action.compute(context),
        "attention": attention[:5],
        "upcoming": upcoming[:4],
        "suggested_guides": guides,
        "similar_historical_count": similar_count,
        "other_projects": [
            {"id": p.id, "title": p.title, "stage": str(p.stage), "status": str(p.status)}
            for p in projects[1:5]
        ],
        "follow_ups_due": len(follow_ups),
    }
