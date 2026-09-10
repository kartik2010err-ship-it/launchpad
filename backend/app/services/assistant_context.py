"""Assemble everything the Research Assistant should already know (section 11).

A student opening the chat inside a project should never have to re-explain that
project. This module gathers the structured facts the app has already collected
— the question, the interview answers, the latest evaluation, the timeline, the
safety screen — into one dictionary the provider can read.

Two deliberate constraints:

* **Only what is on record.** Every field here is read from the database. Nothing
  is inferred, and a field the student has not filled in is reported as missing
  rather than guessed. That is what lets the assistant say "you haven't defined a
  control yet" instead of imagining one.
* **Bounded.** Free text is truncated per field. A notebook with two hundred
  entries must not turn one chat turn into a fifty-thousand-token prompt.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import TaskStatus
from app.models.project import Project
from app.models.workspace import NotebookEntry, TimelineTask
from app.services import project_service
from app.services.signals import ProjectSignals

# Per-field truncation. Long enough to carry a real answer, short enough that a
# fully-answered project still fits comfortably in one prompt.
_FIELD_CHARS = 600
_MAX_NOTEBOOK = 3

# Interview keys grouped the way a student thinks about them, so the context
# chip row can say "variables: defined" rather than listing raw keys.
_FIELD_LABELS: dict[str, str] = {
    "goal": "Goal",
    "independent_variable": "Independent variable",
    "dependent_variable": "Dependent variable",
    "measurement": "Measurement",
    "population": "Population / sample",
    "prediction": "Prediction",
    "mechanism": "Mechanism",
    "control": "Control",
    "trials": "Trials",
    "resources": "Resources",
    "time_budget": "Time budget",
    "regulated": "Regulated materials",
    "prior_work": "Prior work",
    "differentiator": "Differentiator",
    "problem": "Problem",
    "who_experiences": "Who experiences it",
    "constraints": "Design constraints",
    "existing_solutions": "Existing solutions",
    "existing_weaknesses": "Weaknesses of existing solutions",
    "success_metric": "Success metric",
    "alternatives": "Alternatives considered",
    "prototype": "Prototype",
    "test_method": "Test method",
    "comparison_metric": "Comparison metric",
}


def _clip(text: str | None, limit: int = _FIELD_CHARS) -> str | None:
    value = (text or "").strip()
    if not value:
        return None
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _next_deadline(db: Session, project_id: int, today: date | None = None) -> TimelineTask | None:
    today = today or date.today()
    rows = db.scalars(
        select(TimelineTask)
        .where(TimelineTask.project_id == project_id)
        .where(TimelineTask.status != TaskStatus.COMPLETE)
        .where(TimelineTask.due_date.is_not(None))
        .order_by(TimelineTask.due_date)
    ).all()
    return rows[0] if rows else None


def build(db: Session, project: Project) -> dict:
    """The full context payload. Safe to hand straight to a provider."""

    signals: ProjectSignals = project_service.signals_for(project)
    answers = project_service.collect_answers(project)

    known: dict[str, str] = {}
    missing: list[str] = []
    for key in signals.required_keys:
        if signals.has(key):
            known[key] = _clip(answers.get(key)) or ""
        else:
            missing.append(_FIELD_LABELS.get(key, key.replace("_", " ")))

    evaluation = project_service.latest_evaluation(db, project.id)
    evaluation_block: dict | None = None
    if evaluation is not None:
        # Only the shape the assistant can reason about — not the whole blob.
        evaluation_block = {
            "overall_score": evaluation.overall_score,
            "information_completeness": evaluation.information_completeness,
            "dimensions": {
                d.get("key"): d.get("score")
                for d in (evaluation.dimensions or [])
                if isinstance(d, dict) and d.get("key") is not None
            },
            "weak_criteria": _weak_criteria(evaluation.dimensions or []),
            "novelty_status": (evaluation.novelty or {}).get("status"),
            "novelty_reasoning": _clip((evaluation.novelty or {}).get("reasoning"), 400),
            "safety_flags": [
                f.get("label") or f.get("term")
                for f in (evaluation.safety or {}).get("flags", [])
                if isinstance(f, dict)
            ],
            "rubric_total": (evaluation.rubric or {}).get("total"),
            "mentor_summary": _clip(evaluation.mentor_summary, 500),
        }

    upcoming = _next_deadline(db, project.id)
    notebook = db.scalars(
        select(NotebookEntry)
        .where(NotebookEntry.project_id == project.id)
        .order_by(NotebookEntry.entry_date.desc())
        .limit(_MAX_NOTEBOOK)
    ).all()

    return {
        "project_id": project.id,
        "title": project.title,
        "question": project.current_question,
        "topic": _clip(project.topic),
        "background_knowledge": _clip(project.background_knowledge),
        "project_type": str(project.project_type),
        "category": str(project.category),
        "grade_level": project.grade_level,
        "stage": str(project.stage),
        "competition": project.competition_name,
        "competition_date": project.competition_date.isoformat()
        if project.competition_date
        else None,
        "teammates": project.teammates,
        "trials_planned": project.trials_planned,
        "question_issues": signals.question_analysis.issues,
        "information_completeness": signals.completeness,
        "known": known,
        "missing": missing,
        "derived": {
            "quantitative_outcome": signals.quantitative_outcome,
            "control_defined": signals.control_defined,
            "mechanism_explained": signals.mechanism_explained,
            "literature_grounded": signals.literature_grounded,
            "differentiator_stated": signals.differentiator_stated,
            "stats_aware": signals.stats_aware,
            "rigour_markers": signals.rigour_markers,
        },
        "evaluation": evaluation_block,
        "next_deadline": (
            {
                "title": upcoming.title,
                "due_date": upcoming.due_date.isoformat() if upcoming.due_date else None,
                "phase": str(upcoming.phase),
            }
            if upcoming is not None
            else None
        ),
        "recent_notebook": [
            {
                "date": entry.entry_date.isoformat(),
                "what_was_done": _clip(entry.what_was_done, 300),
                "problems": _clip(entry.problems, 200),
            }
            for entry in notebook
        ],
    }


def _weak_criteria(dimensions: list) -> list[dict]:
    """Criteria scoring below 70, worst first — the assistant's list of things
    worth challenging the student about."""

    out: list[dict] = []
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            continue
        for criterion, score in (dimension.get("criteria") or {}).items():
            if isinstance(score, int) and score < 70:
                out.append(
                    {
                        "dimension": dimension.get("key"),
                        "criterion": criterion,
                        "score": score,
                    }
                )
    out.sort(key=lambda row: row["score"])
    return out[:8]


def summarise_for_ui(context: dict) -> dict:
    """The chip row: what the student can see the assistant was given."""

    evaluation = context.get("evaluation") or {}
    known = context.get("known") or {}
    missing = context.get("missing") or []
    deadline = context.get("next_deadline") or {}
    return {
        "project_id": context["project_id"],
        "title": context["title"],
        "question": context["question"],
        "project_type": context["project_type"],
        "category": context["category"],
        "grade_level": context["grade_level"],
        "stage": context["stage"],
        "competition": context.get("competition"),
        "readiness": evaluation.get("overall_score"),
        "answered_count": len(known),
        "total_questions": len(known) + len(missing),
        "known_fields": [_FIELD_LABELS.get(k, k.replace("_", " ")) for k in known],
        "missing_fields": missing,
        "safety_flags": evaluation.get("safety_flags") or [],
        "next_deadline": deadline.get("due_date"),
    }
