"""Business logic layer.

Routers do HTTP; this module does the work. It is the only place that knows how
to assemble signals from persisted interview turns, when to write a new
evaluation row, and how a selected question variant becomes a new revision.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Stage, TaskStatus
from app.models.project import InterviewTurn, Project, QuestionRevision
from app.models.workspace import Evaluation, MockJudgeSession, PosterDraft, ResearchPlan, TimelineTask
from app.schemas.evaluation import EvaluationResult, InterviewStep
from app.services import poster as poster_service
from app.services import timeline as timeline_service
from app.services.ai.factory import get_provider
from app.services.signals import ProjectSignals, build_signals


def collect_answers(project: Project) -> dict[str, str]:
    return {
        turn.question_key: turn.answer_text
        for turn in project.interview_turns
        if turn.answer_text
    }


def signals_for(project: Project) -> ProjectSignals:
    return build_signals(project, collect_answers(project))


def has_poster_draft(db: Session, project_id: int) -> bool:
    draft = db.scalar(select(PosterDraft).where(PosterDraft.project_id == project_id))
    return bool(draft and any(v.strip() for v in (draft.sections or {}).values()))


def mock_interview_done(db: Session, project_id: int) -> bool:
    return bool(
        db.scalar(
            select(MockJudgeSession).where(
                MockJudgeSession.project_id == project_id, MockJudgeSession.finished.is_(True)
            )
        )
    )


# --------------------------------------------------------------------------- #
# Interview
# --------------------------------------------------------------------------- #


def record_answers(db: Session, project: Project, answers: list) -> list[str]:
    keys: list[str] = []
    from app.models.project import utcnow

    for item in answers:
        turn = next(
            (t for t in project.interview_turns if t.question_key == item.question_key),
            None,
        )
        if turn is None:
            turn = InterviewTurn(
                project_id=project.id,
                question_key=item.question_key,
                question_text=item.question_key.replace("_", " ").capitalize(),
                dimension="unknown",
            )
            db.add(turn)
            project.interview_turns.append(turn)
        turn.answer_text = item.answer
        turn.answered_at = utcnow()
        keys.append(item.question_key)
    db.flush()
    return keys


def advance_interview(db: Session, project: Project, answered_keys: list[str], max_questions: int) -> InterviewStep:
    provider = get_provider()
    signals = signals_for(project)
    step = provider.next_questions(signals, max_questions, answered_keys)

    existing = {t.question_key for t in project.interview_turns}
    for question in step.questions:
        if question.key in existing:
            continue
        db.add(InterviewTurn(
            project_id=project.id,
            question_key=question.key,
            question_text=question.text,
            dimension=question.dimension,
            why_asked=question.why_asked,
        ))
    for critique in step.critiques:
        turn = next((t for t in project.interview_turns if t.question_key == critique.question_key), None)
        if turn:
            turn.followup_note = critique.follow_up or critique.note

    if project.stage == Stage.IDEA and answered_keys:
        project.stage = Stage.QUESTION_REFINEMENT
    db.flush()
    return step


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #


def evaluate(db: Session, project: Project) -> tuple[EvaluationResult, Evaluation]:
    provider = get_provider()
    signals = signals_for(project)
    result = provider.evaluate(
        signals,
        Stage(project.stage),
        has_poster_draft(db, project.id),
        mock_interview_done(db, project.id),
    )

    row = Evaluation(
        project_id=project.id,
        provider=result.provider,
        question_snapshot=project.current_question,
        overall_score=result.overall_score,
        information_completeness=result.information_completeness,
        dimensions=[d.model_dump() for d in result.dimensions],
        rubric=result.rubric.model_dump(),
        novelty=result.novelty.model_dump(),
        safety=result.safety.model_dump(),
        signals=signals.coverage,
        mentor_summary=result.mentor_summary,
        next_actions=result.next_actions,
        socratic_questions=result.socratic_questions,
    )
    db.add(row)

    # Stage nudges are suggestions the student can override in the UI.
    if result.safety.preapproval_possible and project.stage in (Stage.IDEA, Stage.QUESTION_REFINEMENT):
        project.stage = Stage.APPROVAL_REQUIRED
    elif result.information_completeness >= 70 and project.stage == Stage.QUESTION_REFINEMENT:
        project.stage = Stage.EXPERIMENTAL_DESIGN

    db.flush()
    return result, row


def latest_evaluation(db: Session, project_id: int) -> Evaluation | None:
    return db.scalar(
        select(Evaluation)
        .where(Evaluation.project_id == project_id)
        .order_by(Evaluation.created_at.desc(), Evaluation.id.desc())
    )


# --------------------------------------------------------------------------- #
# Question revisions
# --------------------------------------------------------------------------- #


def add_revision(
    db: Session,
    project: Project,
    text: str,
    source: str,
    variant: str | None = None,
    rationale: str | None = None,
    improvements: list[str] | None = None,
) -> QuestionRevision:
    next_version = max((r.version for r in project.revisions), default=0) + 1
    revision = QuestionRevision(
        project_id=project.id,
        version=next_version,
        text=text,
        source=source,
        variant=variant,
        rationale=rationale,
        improvements=improvements or [],
    )
    db.add(revision)
    project.revisions.append(revision)
    project.current_question = text
    db.flush()
    return revision


def downstream_impact(db: Session, project: Project) -> list[str]:
    """Section 35: which timeline work a question change invalidates."""
    keys = timeline_service.recompute_downstream("research_question")
    tasks = db.scalars(
        select(TimelineTask).where(
            TimelineTask.project_id == project.id, TimelineTask.key.in_(keys)
        )
    ).all()
    reopened = []
    for task in tasks:
        if task.status == TaskStatus.COMPLETE:
            task.status = TaskStatus.NEEDS_MENTOR_REVIEW
            task.ai_note = "Reopened: your research question changed after this was completed."
            reopened.append(task.title)
    db.flush()
    return reopened


# --------------------------------------------------------------------------- #
# Plans, poster, timeline
# --------------------------------------------------------------------------- #


def build_plan(db: Session, project: Project, question: str | None = None) -> ResearchPlan:
    provider = get_provider()
    signals = signals_for(project)
    doc = provider.research_plan(signals, question or project.current_question)
    row = ResearchPlan(
        project_id=project.id,
        question=question or project.current_question,
        content=doc.model_dump(),
        provider=getattr(provider, "name", "heuristic"),
    )
    db.add(row)
    db.flush()
    return row


def get_or_create_poster(db: Session, project_id: int) -> PosterDraft:
    draft = db.scalar(select(PosterDraft).where(PosterDraft.project_id == project_id))
    if draft is None:
        draft = PosterDraft(project_id=project_id, sections={})
        db.add(draft)
        db.flush()
    return draft


def poster_critique(db: Session, project: Project):
    draft = get_or_create_poster(db, project.id)
    return poster_service.critique(signals_for(project), draft.sections or {})


def regenerate_timeline(db: Session, project: Project, request, today: date | None = None) -> list[TimelineTask]:
    today = today or date.today()
    signals = signals_for(project)
    evaluation = latest_evaluation(db, project.id)
    regulated = bool(evaluation and evaluation.safety.get("preapproval_possible"))
    if not evaluation:
        from app.services.safety import screen

        regulated = screen(signals.any_text()).preapproval_possible

    generated, warnings = timeline_service.generate(
        signals,
        competition_date=request.competition_date,
        today=today,
        hours_per_week=request.hours_per_week,
        trials=request.trials_planned,
        minutes_per_trial=request.minutes_per_trial,
        teammates=request.teammates,
        regulated=regulated,
        already_experimenting=request.already_experimenting,
        school_deadline=request.school_deadline,
    )

    existing = {t.key: t for t in db.scalars(select(TimelineTask).where(TimelineTask.project_id == project.id))}
    rows: list[TimelineTask] = []
    for index, item in enumerate(generated):
        row = existing.pop(item.template.key, None)
        if row is None:
            row = TimelineTask(project_id=project.id, key=item.template.key)
            db.add(row)
        row.phase = item.template.phase
        row.phase_index = index
        row.title = item.template.title
        row.description = item.template.description
        row.start_date = item.start_date
        row.due_date = item.due_date
        row.priority = item.template.priority
        row.estimated_hours = item.hours
        row.depends_on = item.template.depends_on
        row.requirement_source = item.template.source
        row.ai_note = item.ai_note
        rows.append(row)

    # Tasks that no longer apply (e.g. SRC review after the project stopped being regulated)
    for orphan in existing.values():
        if orphan.status == TaskStatus.NOT_STARTED:
            db.delete(orphan)

    project.competition_key = request.competition_key
    project.competition_name = request.competition_name
    project.competition_date = request.competition_date
    project.school_deadline = request.school_deadline
    project.hours_per_week = request.hours_per_week
    project.trials_planned = request.trials_planned
    project.minutes_per_trial = request.minutes_per_trial
    project.teammates = request.teammates
    project.already_experimenting = request.already_experimenting
    db.flush()
    return rows, warnings
