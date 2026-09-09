"""Competition readiness and the weekly planner (sections 19-20, 34).

Readiness is a completion estimate, not a score. It mixes two things
deliberately: how good the design is (from the evaluation) and how much of the
work is done (from the timeline). A brilliant question with nothing built is not
ready, and neither is a finished poster on a broken design.
"""

from __future__ import annotations

from datetime import date

from app.models.enums import Phase, Priority, TaskStatus
from app.schemas.project import ReadinessArea, ReadinessOut

DISCLAIMER = (
    "A project-completion estimate produced by this app. It is not an official competition score "
    "and no judge has seen your work."
)

PRIORITY_RANK = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}

AREA_PHASES = {
    "research_question": [Phase.IDEA],
    "methodology": [Phase.DESIGN],
    "experimentation": [Phase.EXPERIMENTATION],
    "analysis": [Phase.ANALYSIS, Phase.WRITE_UP],
    "poster": [Phase.POSTER],
    "interview": [Phase.INTERVIEW],
    "forms": [Phase.RULES, Phase.COMPETITION],
}

AREA_LABELS = {
    "research_question": "Research question",
    "methodology": "Methodology",
    "experimentation": "Experimentation",
    "analysis": "Analysis",
    "poster": "Poster",
    "interview": "Interview",
    "forms": "Forms and rules",
}

# How much each area counts toward the overall figure.
AREA_WEIGHTS = {
    "research_question": 0.15,
    "methodology": 0.15,
    "experimentation": 0.20,
    "analysis": 0.15,
    "poster": 0.15,
    "interview": 0.12,
    "forms": 0.08,
}


def _task_completion(tasks, phases) -> int | None:
    relevant = [t for t in tasks if t.phase in {str(p) for p in phases}]
    if not relevant:
        return None
    done = sum(1 for t in relevant if t.status == TaskStatus.COMPLETE)
    partial = sum(0.4 for t in relevant if t.status == TaskStatus.IN_PROGRESS)
    return round(100 * (done + partial) / len(relevant))


def compute(tasks, evaluation, poster_score: int | None) -> ReadinessOut:
    dims = {d["key"]: d["score"] for d in (evaluation.dimensions if evaluation else [])}
    areas: list[ReadinessArea] = []

    for key, phases in AREA_PHASES.items():
        task_pct = _task_completion(tasks, phases)
        design_pct = None
        note = ""

        if key == "research_question":
            design_pct = dims.get("research_question")
            note = "Blends question quality with the idea-phase tasks you have closed."
        elif key == "methodology":
            design_pct = dims.get("methodology")
            note = "Design quality plus how much of the design work is finished."
        elif key == "poster" and poster_score is not None:
            design_pct = poster_score
            note = "Draft quality plus poster tasks completed."
        elif key == "experimentation":
            note = "Purely task completion — no evaluation can substitute for running trials."
        elif key == "analysis":
            note = "Counts analysis and write-up tasks."
        elif key == "interview":
            note = "Practice is the only thing that moves this."
        elif key == "forms":
            note = "Rules, approvals and competition-day checks."

        parts = [p for p in (task_pct, design_pct) if p is not None]
        percent = round(sum(parts) / len(parts)) if parts else 0
        areas.append(ReadinessArea(key=key, label=AREA_LABELS[key], percent=percent, note=note))

    overall = round(sum(a.percent * AREA_WEIGHTS[a.key] for a in areas))
    return ReadinessOut(areas=areas, overall=overall, disclaimer=DISCLAIMER)


def weekly_priorities(tasks, today: date, limit: int = 5) -> list:
    """Rank by: blocked-and-critical first, then unblocked work by due date."""
    done_keys = {t.key for t in tasks if t.status == TaskStatus.COMPLETE}
    open_tasks = [t for t in tasks if t.status != TaskStatus.COMPLETE]

    def unblocked(task) -> bool:
        return all(dep in done_keys for dep in (task.depends_on or []))

    def sort_key(task):
        overdue = 0 if task.due_date and task.due_date < today else 1
        return (
            0 if not unblocked(task) and task.priority == Priority.CRITICAL else 1,
            overdue,
            PRIORITY_RANK.get(Priority(task.priority), 2),
            task.due_date or date.max,
        )

    ready = [t for t in open_tasks if unblocked(t)]
    stuck_critical = [t for t in open_tasks if not unblocked(t) and t.priority == Priority.CRITICAL]
    ordered = sorted(stuck_critical + ready, key=sort_key)
    return ordered[:limit]


def blockers(tasks) -> list:
    return [
        t
        for t in tasks
        if t.status in (TaskStatus.BLOCKED, TaskStatus.NEEDS_MENTOR_REVIEW)
    ]


def completion_percent(tasks) -> int:
    if not tasks:
        return 0
    done = sum(1 for t in tasks if t.status == TaskStatus.COMPLETE)
    return round(100 * done / len(tasks))
