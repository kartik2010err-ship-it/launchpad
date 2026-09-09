from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_project
from app.db.session import get_db
from app.models.enums import TaskStatus
from app.models.project import Project
from app.models.workspace import MentorComment, TimelineTask
from app.schemas.project import (
    ReadinessOut,
    TimelineOut,
    TimelineRequest,
    TimelineTaskOut,
    TimelineTaskUpdate,
    WeeklyPlan,
)
from app.services import competitions, project_service, readiness

router = APIRouter(tags=["planning"])

DISCLAIMER = (
    "Items marked as competition requirements have not been verified against an official rulebook. "
    "Confirm every deadline and form with the competition website or your advisor."
)


@router.get("/competitions")
def list_competitions() -> list[dict]:
    return competitions.listing()


@router.get("/competitions/{key}")
def competition_detail(key: str) -> dict:
    comp = competitions.get(key)
    return {
        "key": comp.key,
        "name": comp.name,
        "official_source_loaded": comp.official_source_loaded,
        "notice": comp.notice,
        "items": [
            {
                "key": i.key,
                "label": i.label,
                "source": i.source,
                "days_before_fair": i.days_before_fair,
                "note": i.note,
            }
            for i in comp.items
        ],
        # Team configuration lives alongside the requirements so the UI can show
        # "what this app enforces" next to "what the rulebook says" — which is
        # unloaded, and labelled as such.
        "team_rules": competitions.team_rules_payload(comp.key),
    }


@router.post("/projects/{project_id}/timeline", response_model=TimelineOut)
def generate_timeline(
    payload: TimelineRequest,
    project: Project = Depends(get_project),
    db: Session = Depends(get_db),
) -> TimelineOut:
    if payload.competition_date <= date.today():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The competition date needs to be in the future.")
    tasks, warnings = project_service.regenerate_timeline(db, project, payload)
    db.commit()
    total_hours = sum(t.estimated_hours for t in tasks)
    days = (payload.competition_date - date.today()).days
    return TimelineOut(
        tasks=[TimelineTaskOut.model_validate(t) for t in tasks],
        warnings=warnings,
        total_estimated_hours=round(total_hours, 1),
        available_hours=round(payload.hours_per_week * days / 7, 1),
        days_remaining=days,
        competition_name=project.competition_name or competitions.get(payload.competition_key).name,
        competition_date=payload.competition_date,
        requirement_disclaimer=DISCLAIMER,
    )


@router.get("/projects/{project_id}/timeline", response_model=TimelineOut)
def get_timeline(project: Project = Depends(get_project), db: Session = Depends(get_db)) -> TimelineOut:
    tasks = list(
        db.scalars(
            select(TimelineTask)
            .where(TimelineTask.project_id == project.id)
            .order_by(TimelineTask.phase_index)
        )
    )
    days = (project.competition_date - date.today()).days if project.competition_date else 0
    return TimelineOut(
        tasks=[TimelineTaskOut.model_validate(t) for t in tasks],
        warnings=[],
        total_estimated_hours=round(sum(t.estimated_hours for t in tasks), 1),
        available_hours=round((project.hours_per_week or 0) * days / 7, 1),
        days_remaining=days,
        competition_name=project.competition_name,
        competition_date=project.competition_date,
        requirement_disclaimer=DISCLAIMER,
    )


@router.patch("/projects/{project_id}/tasks/{task_id}", response_model=TimelineTaskOut)
def update_task(
    task_id: int,
    payload: TimelineTaskUpdate,
    project: Project = Depends(get_project),
    db: Session = Depends(get_db),
) -> TimelineTask:
    task = db.get(TimelineTask, task_id)
    if task is None or task.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    if payload.status == TaskStatus.COMPLETE:
        from app.models.project import utcnow

        task.completed_at = utcnow()
    db.commit()
    db.refresh(task)
    return task


@router.get("/projects/{project_id}/readiness", response_model=ReadinessOut)
def get_readiness(project: Project = Depends(get_project), db: Session = Depends(get_db)) -> ReadinessOut:
    tasks = list(db.scalars(select(TimelineTask).where(TimelineTask.project_id == project.id)))
    evaluation = project_service.latest_evaluation(db, project.id)
    poster_score = None
    if project_service.has_poster_draft(db, project.id):
        poster_score = project_service.poster_critique(db, project).score
    return readiness.compute(tasks, evaluation, poster_score)


@router.get("/projects/{project_id}/this-week", response_model=WeeklyPlan)
def this_week(project: Project = Depends(get_project), db: Session = Depends(get_db)) -> WeeklyPlan:
    today = date.today()
    tasks = list(db.scalars(select(TimelineTask).where(TimelineTask.project_id == project.id)))
    evaluation = project_service.latest_evaluation(db, project.id)

    risk_notes: list[str] = []
    if evaluation and evaluation.safety.get("preapproval_possible"):
        labels = ", ".join(f["label"] for f in evaluation.safety.get("flags", []))
        risk_notes.append(
            f"Your project may require approval before experimentation ({labels}). "
            "Verify with your sponsor before collecting any data."
        )
    if evaluation and evaluation.information_completeness < 60:
        risk_notes.append(
            "Your evaluation is based on an incomplete interview, so the scores understate or "
            "overstate the project. Finish the interview to get a usable reading."
        )
    upcoming = [t.due_date for t in tasks if t.due_date and t.status != TaskStatus.COMPLETE]

    open_comments = list(
        db.scalars(
            select(MentorComment).where(
                MentorComment.project_id == project.id,
                MentorComment.requires_action.is_(True),
                MentorComment.resolved.is_(False),
            )
        )
    )

    return WeeklyPlan(
        priorities=[TimelineTaskOut.model_validate(t) for t in readiness.weekly_priorities(tasks, today)],
        upcoming_deadline=min(upcoming) if upcoming else project.competition_date,
        days_remaining=(project.competition_date - today).days if project.competition_date else None,
        completion_percent=readiness.completion_percent(tasks),
        blockers=[TimelineTaskOut.model_validate(t) for t in readiness.blockers(tasks)],
        mentor_requests=open_comments,
        risk_notes=risk_notes,
    )


@router.get("/projects/{project_id}/checklist")
def checklist(project: Project = Depends(get_project), db: Session = Depends(get_db)) -> dict:
    """Section 33 — derived from the timeline so it can never drift out of sync."""
    tasks = list(db.scalars(select(TimelineTask).where(TimelineTask.project_id == project.id)))
    groups: dict[str, list[dict]] = {}
    for task in tasks:
        groups.setdefault(str(task.phase), []).append(
            {
                "key": task.key,
                "label": task.title,
                "done": task.status == TaskStatus.COMPLETE,
                "source": task.requirement_source,
                "due_date": task.due_date,
            }
        )
    return {"groups": groups, "disclaimer": DISCLAIMER}
