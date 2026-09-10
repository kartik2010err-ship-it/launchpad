from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_editable_project, get_project
from app.db.session import get_db
from app.models.enums import ActivityKind, Stage
from app.models.project import Project, User
from app.models.workspace import Evaluation, MentorComment, ResearchPlan
from app.schemas.evaluation import EvaluationResult, InterviewStep, RefinementResult
from app.schemas.project import (
    EvaluationOut,
    InterviewSubmission,
    MentorCommentCreate,
    MentorCommentOut,
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    ProjectUpdate,
    ResearchPlanOut,
    ScoreHistoryPoint,
    SelectVariant,
)
from app.services import (
    activity_service,
    project_service,
    project_status_service,
    workspace_service,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Project:
    workspace = workspace_service.resolve_target_workspace(db, user, payload.workspace_id)
    project = Project(
        owner_id=user.id,
        workspace_id=workspace.id,
        visibility=workspace.default_project_visibility,
        title=payload.title,
        topic=payload.topic,
        grade_level=payload.grade_level,
        project_type=payload.project_type,
        category=payload.category,
        background_knowledge=payload.background_knowledge,
        current_question=payload.initial_question,
        stage=Stage.IDEA,
    )
    db.add(project)
    db.flush()
    project_service.add_revision(
        db, project, payload.initial_question, source="student",
        rationale="Your starting question, kept for the record.",
    )
    # Open the interview immediately so the first screen is a question, not a form.
    project_service.advance_interview(db, project, [], max_questions=3)
    project_status_service.refresh(db, project)
    activity_service.record(
        db,
        project=project,
        actor=user,
        action="project_created",
        summary=f"{user.name} started {project.title}",
        kind=ActivityKind.MILESTONE,
    )
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectSummary])
def list_projects(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    workspace_id: int | None = None,
):
    """Every project the caller may open, across all their workspaces.

    Visibility is decided per project by the same predicate the detail route
    uses, so this list can never contain something the caller would be 403'd
    out of.
    """

    out: list[Project] = []
    for workspace in workspace_service.workspaces_for(db, user.id):
        if workspace_id is not None and workspace.id != workspace_id:
            continue
        membership = workspace_service.membership_for(db, workspace.id, user.id)
        stmt = (
            select(Project)
            .where(Project.workspace_id == workspace.id)
            .order_by(Project.updated_at.desc())
        )
        out.extend(
            p
            for p in db.scalars(stmt)
            if workspace_service.can_view_project(db, p, membership)
        )
    out.sort(key=lambda p: p.updated_at, reverse=True)
    return out


@router.get("/{project_id}", response_model=ProjectDetail)
def get_one(project: Project = Depends(get_project)) -> Project:
    return project


@router.patch("/{project_id}", response_model=ProjectDetail)
def update_project(
    payload: ProjectUpdate,
    project: Project = Depends(get_editable_project),
    db: Session = Depends(get_db),
) -> Project:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


# --------------------------------------------------------------------------- #
# Interview
# --------------------------------------------------------------------------- #


@router.post("/{project_id}/interview", response_model=InterviewStep)
def interview(
    payload: InterviewSubmission,
    project: Project = Depends(get_project),
    db: Session = Depends(get_db),
) -> InterviewStep:
    answered = project_service.record_answers(db, project, payload.answers)
    step = project_service.advance_interview(db, project, answered, payload.max_questions)
    db.commit()
    return step


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #


@router.post("/{project_id}/evaluate", response_model=EvaluationResult)
def evaluate(project: Project = Depends(get_project), db: Session = Depends(get_db)) -> EvaluationResult:
    result, _row = project_service.evaluate(db, project)
    db.commit()
    return result


@router.get("/{project_id}/evaluation", response_model=EvaluationOut)
def latest(project: Project = Depends(get_project), db: Session = Depends(get_db)) -> Evaluation:
    row = project_service.latest_evaluation(db, project.id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This project has not been evaluated yet.")
    return row


@router.get("/{project_id}/rubric")
def rubric(project: Project = Depends(get_project), db: Session = Depends(get_db)) -> dict:
    row = project_service.latest_evaluation(db, project.id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run an evaluation first.")
    return row.rubric


@router.get("/{project_id}/novelty")
def novelty(project: Project = Depends(get_project), db: Session = Depends(get_db)) -> dict:
    row = project_service.latest_evaluation(db, project.id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run an evaluation first.")
    return row.novelty


@router.get("/{project_id}/score-history", response_model=list[ScoreHistoryPoint])
def score_history(project: Project = Depends(get_project), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Evaluation).where(Evaluation.project_id == project.id).order_by(Evaluation.created_at)
    ).all()
    return [
        ScoreHistoryPoint(
            created_at=row.created_at,
            overall_score=row.overall_score,
            dimensions={d["key"]: d["score"] for d in row.dimensions},
        )
        for row in rows
    ]


# --------------------------------------------------------------------------- #
# Refinement
# --------------------------------------------------------------------------- #


@router.post("/{project_id}/refine", response_model=RefinementResult)
def refine(project: Project = Depends(get_project)) -> RefinementResult:
    from app.services.ai.factory import get_provider

    return get_provider().refine(project_service.signals_for(project))


@router.post("/{project_id}/question", response_model=ProjectDetail)
def select_question(
    payload: SelectVariant,
    project: Project = Depends(get_editable_project),
    db: Session = Depends(get_db),
) -> Project:
    project_service.add_revision(
        db, project, payload.question,
        source="ai_refinement" if payload.variant else "student",
        variant=payload.variant,
        rationale=payload.rationale,
        improvements=payload.improvements,
    )
    reopened = project_service.downstream_impact(db, project)
    db.commit()
    db.refresh(project)
    if reopened:
        # Surfaced in the response headers so the UI can show the dependency warning.
        project.__dict__["_reopened"] = reopened
    return project


# --------------------------------------------------------------------------- #
# Research plan
# --------------------------------------------------------------------------- #


@router.post("/{project_id}/research-plan", response_model=ResearchPlanOut)
def create_plan(project: Project = Depends(get_project), db: Session = Depends(get_db)) -> ResearchPlan:
    row = project_service.build_plan(db, project)
    db.commit()
    return row


@router.get("/{project_id}/research-plan", response_model=ResearchPlanOut)
def get_plan(project: Project = Depends(get_project), db: Session = Depends(get_db)) -> ResearchPlan:
    row = db.scalar(
        select(ResearchPlan)
        .where(ResearchPlan.project_id == project.id)
        .order_by(ResearchPlan.created_at.desc(), ResearchPlan.id.desc())
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No research plan has been generated yet.")
    return row


# --------------------------------------------------------------------------- #
# Mentor comments
# --------------------------------------------------------------------------- #


@router.post("/{project_id}/mentor-comments", response_model=MentorCommentOut, status_code=201)
def add_comment(
    payload: MentorCommentCreate,
    project: Project = Depends(get_project),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MentorComment:
    membership = workspace_service.membership_for(db, project.workspace_id, user.id)
    if not workspace_service.can_comment_on_project(db, project, membership):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot comment on this project.")
    comment = MentorComment(
        project_id=project.id,
        author_role=membership.role.value,
        author_id=user.id,
        author_name=user.name,
        section=payload.section,
        body=payload.body,
        requires_action=payload.requires_action,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/{project_id}/mentor-comments", response_model=list[MentorCommentOut])
def list_comments(project: Project = Depends(get_project), db: Session = Depends(get_db)):
    return list(
        db.scalars(
            select(MentorComment)
            .where(MentorComment.project_id == project.id)
            .order_by(MentorComment.created_at.desc())
        )
    )


@router.post("/{project_id}/mentor-comments/{comment_id}/resolve", response_model=MentorCommentOut)
def resolve_comment(
    comment_id: int,
    project: Project = Depends(get_project),
    db: Session = Depends(get_db),
) -> MentorComment:
    comment = db.get(MentorComment, comment_id)
    if comment is None or comment.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found.")
    comment.resolved = True
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/home/dashboard", tags=["home"])
def home_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Section 34. The four questions the logged-in home page has to answer."""

    from app.services import home_service

    return home_service.build(db, user)
