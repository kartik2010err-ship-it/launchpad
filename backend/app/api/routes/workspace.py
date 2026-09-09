from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_editable_project, get_project
from app.db.session import get_db
from app.models.project import Project
from app.models.workspace import MockJudgeSession, NotebookEntry, PosterDraft
from app.schemas.evaluation import (
    InterviewPrepSet,
    MockJudgeReply,
    MockJudgeReport,
    PosterCritique,
    PosterPlan,
)
from app.schemas.project import (
    MockJudgeMessage,
    NotebookEntryCreate,
    NotebookEntryOut,
    PosterDraftOut,
    PosterDraftUpdate,
)
from app.services import project_service
from app.services.ai.factory import get_provider

router = APIRouter(prefix="/projects/{project_id}", tags=["workspace"])


# --------------------------------------------------------------------------- #
# Poster
# --------------------------------------------------------------------------- #


@router.get("/poster/plan", response_model=PosterPlan)
def poster_plan(project: Project = Depends(get_project), db: Session = Depends(get_db)) -> PosterPlan:
    plan = get_provider().poster_plan(project_service.signals_for(project))
    draft = project_service.get_or_create_poster(db, project.id)
    db.commit()
    for section in plan.sections:
        text = (draft.sections or {}).get(section.key, "").strip()
        if text:
            section.currently_has = f"{len(text.split())} words drafted."
    return plan


@router.get("/poster", response_model=PosterDraftOut)
def get_poster(project: Project = Depends(get_project), db: Session = Depends(get_db)) -> PosterDraft:
    draft = project_service.get_or_create_poster(db, project.id)
    db.commit()
    return draft


@router.put("/poster", response_model=PosterDraftOut)
def save_poster(
    payload: PosterDraftUpdate,
    project: Project = Depends(get_editable_project),
    db: Session = Depends(get_db),
) -> PosterDraft:
    draft = project_service.get_or_create_poster(db, project.id)
    if payload.layout_key is not None:
        draft.layout_key = payload.layout_key
    draft.sections = {**(draft.sections or {}), **payload.sections}
    db.commit()
    db.refresh(draft)
    return draft


@router.post("/poster/critique", response_model=PosterCritique)
def critique_poster(project: Project = Depends(get_project), db: Session = Depends(get_db)) -> PosterCritique:
    result = project_service.poster_critique(db, project)
    db.commit()
    return result


# --------------------------------------------------------------------------- #
# Interview preparation
# --------------------------------------------------------------------------- #


@router.get("/interview-prep", response_model=InterviewPrepSet)
def interview_prep(project: Project = Depends(get_project)) -> InterviewPrepSet:
    return get_provider().judge_questions(project_service.signals_for(project))


@router.post("/mock-judge", response_model=MockJudgeReply)
def mock_judge(
    payload: MockJudgeMessage,
    project: Project = Depends(get_editable_project),
    db: Session = Depends(get_db),
) -> MockJudgeReply:
    session = db.scalar(
        select(MockJudgeSession)
        .where(MockJudgeSession.project_id == project.id, MockJudgeSession.finished.is_(False))
        .order_by(MockJudgeSession.id.desc())
    )
    if session is None:
        session = MockJudgeSession(project_id=project.id, transcript=[])
        db.add(session)
        db.flush()

    transcript = list(session.transcript or [])
    if payload.answer:
        transcript.append({"role": "student", "text": payload.answer})

    signals = project_service.signals_for(project)
    reply = get_provider().mock_judge_turn(signals, transcript, payload.answer)

    if payload.finish or reply.finished:
        session.finished = True
        session.transcript = transcript
        session.report = get_provider().mock_judge_report(signals, transcript).model_dump()
        db.commit()
        return MockJudgeReply(judge_question="", reaction=reply.reaction, probing="", turn_index=reply.turn_index, finished=True)

    if reply.judge_question:
        transcript.append({"role": "judge", "text": reply.judge_question})
    session.transcript = transcript
    db.commit()
    return reply


@router.get("/mock-judge/report", response_model=MockJudgeReport)
def mock_report(project: Project = Depends(get_project), db: Session = Depends(get_db)) -> MockJudgeReport:
    session = db.scalar(
        select(MockJudgeSession)
        .where(MockJudgeSession.project_id == project.id, MockJudgeSession.finished.is_(True))
        .order_by(MockJudgeSession.id.desc())
    )
    if session is None or not session.report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finish a mock judging session first.")
    return MockJudgeReport.model_validate(session.report)


# --------------------------------------------------------------------------- #
# Research notebook
# --------------------------------------------------------------------------- #


@router.get("/notebook", response_model=list[NotebookEntryOut])
def list_entries(project: Project = Depends(get_project), db: Session = Depends(get_db)):
    return list(
        db.scalars(
            select(NotebookEntry)
            .where(NotebookEntry.project_id == project.id)
            .order_by(NotebookEntry.entry_date.desc(), NotebookEntry.id.desc())
        )
    )


@router.post("/notebook", response_model=NotebookEntryOut, status_code=status.HTTP_201_CREATED)
def add_entry(
    payload: NotebookEntryCreate,
    project: Project = Depends(get_editable_project),
    db: Session = Depends(get_db),
) -> NotebookEntry:
    entry = NotebookEntry(project_id=project.id, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/templates")
def templates(project: Project = Depends(get_project)) -> dict:
    """Section 32 — data tables shaped around this project's own variables."""
    s = project_service.signals_for(project)
    iv = s.get("independent_variable") or s.get("alternatives") or "Independent variable"
    dv = s.get("dependent_variable") or s.get("comparison_metric") or "Measurement"
    engineering = str(project.project_type) == "engineering"

    tables = {
        "trial_data": {
            "title": "Trial data table",
            "columns": ["Trial", "Condition", iv[:40], dv[:40], "Notes", "Error or issue"],
        },
        "source_tracker": {
            "title": "Research source tracker",
            "columns": ["Source", "Key finding", "Relevance to my question", "Citation", "Gap it leaves open"],
        },
        "experiment_log": {
            "title": "Experiment log",
            "columns": ["Date", "Trial", "Procedure change", "Reason", "Result"],
        },
        "judge_questions": {
            "title": "Judge question tracker",
            "columns": ["Question", "My answer", "Weakness", "Improved answer"],
        },
    }
    if engineering:
        tables["prototype_tracker"] = {
            "title": "Prototype tracker",
            "columns": ["Version", "Change", "Reason", "Test result", "Next improvement"],
        }
    return tables
