"""Decides whether a project is on track, and says why.

Deliberately a separate module with pure functions and named constants, because
"at risk" is a club policy question, not a technical one. An advisor who thinks
ten days of silence is fine should be able to change ``INACTIVE_DAYS`` here and
have the whole app agree, including the dashboards, the attention queue and the
status pills.

Every signal produces a human-readable reason. A dashboard that says "at risk"
without saying why just makes an advisor click through to find out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import STAGE_ORDER, ProjectStatus, Stage, TaskStatus
from app.models.project import Project
from app.models.workspace import Evaluation, MentorComment, TimelineTask

# ---- policy knobs -------------------------------------------------------- #

INACTIVE_DAYS = 10  # silence before we flag a student
DEADLINE_SOON_DAYS = 14  # "competition is close" window
DEADLINE_URGENT_DAYS = 7
OVERDUE_AT_RISK = 3  # this many overdue tasks tips into at-risk
LOW_READINESS = 45  # readiness below this, close to a fair, is at-risk
STAGES_NEEDING_APPROVAL = {Stage.APPROVAL_REQUIRED}
# Past this point the club has evidently cleared the paperwork, so an old
# safety flag on the evaluation is a record of what was reviewed, not a blocker.
LAST_STAGE_NEEDING_APPROVAL = Stage.APPROVAL_REQUIRED


def _stage_index(stage: Stage) -> int:
    return STAGE_ORDER.index(stage)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@dataclass
class StatusSignals:
    """Everything the rules looked at, kept so the UI can explain itself."""

    overdue_tasks: int = 0
    blocked_tasks: int = 0
    needs_review_tasks: int = 0
    days_to_deadline: int | None = None
    days_inactive: int = 0
    readiness: int | None = None
    unresolved_safety_flags: int = 0
    awaiting_approval: bool = False
    open_action_comments: int = 0
    has_mentor: bool = True
    next_deadline: date | None = None
    next_task_title: str | None = None


@dataclass
class StatusVerdict:
    status: ProjectStatus
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    signals: StatusSignals = field(default_factory=StatusSignals)

    @property
    def needs_attention(self) -> bool:
        return self.status in {
            ProjectStatus.NEEDS_ATTENTION,
            ProjectStatus.AT_RISK,
            ProjectStatus.BLOCKED,
        }


def gather_signals(db: Session, project: Project, today: date | None = None) -> StatusSignals:
    today = today or date.today()
    signals = StatusSignals()

    tasks = list(
        db.scalars(select(TimelineTask).where(TimelineTask.project_id == project.id))
    )
    upcoming: list[TimelineTask] = []
    for task in tasks:
        if task.status == TaskStatus.COMPLETE:
            continue
        if task.status == TaskStatus.BLOCKED:
            signals.blocked_tasks += 1
        if task.status == TaskStatus.NEEDS_MENTOR_REVIEW:
            signals.needs_review_tasks += 1
        if task.due_date and task.due_date < today:
            signals.overdue_tasks += 1
        elif task.due_date:
            upcoming.append(task)

    upcoming.sort(key=lambda t: t.due_date or date.max)
    if upcoming:
        signals.next_deadline = upcoming[0].due_date
        signals.next_task_title = upcoming[0].title

    if project.competition_date:
        signals.days_to_deadline = (project.competition_date - today).days

    last_seen = _as_aware(project.last_activity_at) or _as_aware(project.updated_at)
    if last_seen:
        signals.days_inactive = max(0, (_utcnow() - last_seen).days)

    evaluation = db.scalars(
        select(Evaluation)
        .where(Evaluation.project_id == project.id)
        .order_by(Evaluation.created_at.desc())
    ).first()
    if evaluation:
        signals.readiness = evaluation.overall_score
        safety = evaluation.safety or {}
        signals.unresolved_safety_flags = len(safety.get("flags", []) or [])

    # Approval is outstanding only while the project is still at or before the
    # approval stage. A project already running trials has plainly cleared it.
    before_or_at_approval = _stage_index(project.stage) <= _stage_index(
        LAST_STAGE_NEEDING_APPROVAL
    )
    signals.awaiting_approval = before_or_at_approval and (
        project.stage in STAGES_NEEDING_APPROVAL or signals.unresolved_safety_flags > 0
    )

    signals.open_action_comments = len(
        list(
            db.scalars(
                select(MentorComment).where(
                    MentorComment.project_id == project.id,
                    MentorComment.requires_action.is_(True),
                    MentorComment.resolved.is_(False),
                )
            )
        )
    )
    signals.has_mentor = project.mentor_id is not None
    return signals


def evaluate(signals: StatusSignals, stage: Stage) -> StatusVerdict:
    """Turn signals into one status. Ordered most severe first."""

    verdict = StatusVerdict(status=ProjectStatus.ON_TRACK, signals=signals)

    if stage == Stage.COMPLETE:
        verdict.status = ProjectStatus.COMPLETE
        verdict.reasons.append("Project is finished.")
        return verdict

    # --- blocked: something external must move before work can continue ---- #
    if signals.blocked_tasks:
        verdict.status = ProjectStatus.BLOCKED
        verdict.blockers.append(
            f"{signals.blocked_tasks} task{'s' if signals.blocked_tasks > 1 else ''} marked blocked."
        )
    if signals.unresolved_safety_flags and signals.awaiting_approval:
        verdict.status = ProjectStatus.BLOCKED
        verdict.blockers.append(
            f"{signals.unresolved_safety_flags} rules/safety flag"
            f"{'s' if signals.unresolved_safety_flags > 1 else ''} still unresolved — "
            "experimentation cannot start until approval is settled."
        )
    if verdict.status == ProjectStatus.BLOCKED:
        return verdict

    # --- at risk: the schedule is genuinely in danger ---------------------- #
    at_risk_reasons: list[str] = []
    if signals.overdue_tasks >= OVERDUE_AT_RISK:
        at_risk_reasons.append(f"{signals.overdue_tasks} overdue tasks.")
    if (
        signals.days_to_deadline is not None
        and signals.days_to_deadline <= DEADLINE_URGENT_DAYS
        and stage
        in {
            Stage.IDEA,
            Stage.QUESTION_REFINEMENT,
            Stage.BACKGROUND_RESEARCH,
            Stage.EXPERIMENTAL_DESIGN,
            Stage.APPROVAL_REQUIRED,
        }
    ):
        at_risk_reasons.append(
            f"Competition is {signals.days_to_deadline} days away and experimentation "
            "has not started."
        )
    if (
        signals.readiness is not None
        and signals.readiness < LOW_READINESS
        and signals.days_to_deadline is not None
        and signals.days_to_deadline <= DEADLINE_SOON_DAYS
    ):
        at_risk_reasons.append(
            f"Readiness is {signals.readiness}/100 with {signals.days_to_deadline} days left."
        )
    if signals.days_inactive >= INACTIVE_DAYS * 2:
        at_risk_reasons.append(f"No activity for {signals.days_inactive} days.")

    if at_risk_reasons:
        verdict.status = ProjectStatus.AT_RISK
        verdict.reasons.extend(at_risk_reasons)
        return verdict

    # --- needs attention: worth a nudge, not yet a crisis ------------------ #
    attention: list[str] = []
    if signals.overdue_tasks:
        attention.append(
            f"{signals.overdue_tasks} overdue task{'s' if signals.overdue_tasks > 1 else ''}."
        )
    if signals.days_inactive >= INACTIVE_DAYS:
        attention.append(f"Quiet for {signals.days_inactive} days.")
    if signals.needs_review_tasks:
        attention.append(f"{signals.needs_review_tasks} item(s) waiting on mentor review.")
    if signals.open_action_comments:
        attention.append(
            f"{signals.open_action_comments} mentor comment(s) still need a response."
        )
    if signals.awaiting_approval:
        attention.append("Approval paperwork is still outstanding.")
    if not signals.has_mentor:
        attention.append("No mentor assigned yet.")
    if (
        signals.days_to_deadline is not None
        and 0 <= signals.days_to_deadline <= DEADLINE_SOON_DAYS
    ):
        attention.append(f"Competition in {signals.days_to_deadline} days.")

    if attention:
        verdict.status = ProjectStatus.NEEDS_ATTENTION
        verdict.reasons.extend(attention)
    else:
        verdict.reasons.append("No overdue work, approvals settled, recently active.")
    return verdict


def compute(db: Session, project: Project, today: date | None = None) -> StatusVerdict:
    return evaluate(gather_signals(db, project, today), project.stage)


def refresh(db: Session, project: Project, today: date | None = None) -> StatusVerdict:
    """Compute and persist. Cheap enough to call whenever a project changes."""

    verdict = compute(db, project, today)
    project.status = verdict.status
    db.flush()
    return verdict
