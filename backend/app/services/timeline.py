"""Timeline generation (sections 17-18, 35).

The scheduler works backwards from the fair date and forwards from today, then
compares the two. It does not divide the available days evenly, because the
phases are not interchangeable:

* approval must finish before regulated experimentation may begin,
* experimentation must finish before analysis can start,
* the main figure must exist before the poster is finalised,
* the poster must exist before interview practice is worth anything.

Effort is estimated from what the student told us (trial count × minutes per
trial, teammates, hours per week) rather than from a fixed template, so the
warnings are about their plan and not a generic one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.models.enums import Phase, Priority, RequirementSource, TaskStatus
from app.schemas.project import TimelineWarning
from app.services.signals import ProjectSignals


@dataclass
class TaskTemplate:
    key: str
    phase: Phase
    title: str
    description: str
    hours: float
    depends_on: list[str]
    priority: Priority = Priority.MEDIUM
    source: RequirementSource = RequirementSource.RECOMMENDED_CLUB_MILESTONE
    only_if_regulated: bool = False


TEMPLATES: list[TaskTemplate] = [
    # Phase 1
    TaskTemplate("pick_topic", Phase.IDEA, "Settle the topic", "Commit to one topic so background reading stops being scattered.", 2, [], Priority.HIGH),
    TaskTemplate("background_read", Phase.IDEA, "Preliminary background research", "Find and summarise at least three sources; record what each leaves open.", 6, ["pick_topic"], Priority.HIGH),
    TaskTemplate("refine_question", Phase.IDEA, "Refine the research question", "Rewrite until the question names a variable, a population and a measurement.", 3, ["background_read"], Priority.CRITICAL),
    TaskTemplate("novelty_check", Phase.IDEA, "Identify what is new", "Write one paragraph on what your version does that existing work does not.", 2, ["background_read"]),
    TaskTemplate("hypothesis", Phase.IDEA, "Define hypothesis or engineering goal", "State a prediction you could be wrong about, with reasoning.", 2, ["refine_question"], Priority.HIGH),

    # Phase 2
    TaskTemplate("classify", Phase.RULES, "Determine project classification and required forms", "Work out which rules category your project falls into.", 2, ["refine_question"], Priority.CRITICAL, RequirementSource.UNVERIFIED_COMPETITION_ITEM),
    TaskTemplate("write_plan", Phase.RULES, "Complete the written research plan", "The document your sponsor and SRC review.", 5, ["hypothesis"], Priority.CRITICAL, RequirementSource.UNVERIFIED_COMPETITION_ITEM),
    TaskTemplate("sponsor_approval", Phase.RULES, "Obtain teacher or sponsor approval", "Do not schedule experimentation before this is signed.", 3, ["write_plan"], Priority.CRITICAL, RequirementSource.UNVERIFIED_COMPETITION_ITEM),
    TaskTemplate("src_irb", Phase.RULES, "Complete SRC or IRB review", "Required for regulated projects. Allow weeks, not days.", 6, ["write_plan"], Priority.CRITICAL, RequirementSource.UNVERIFIED_COMPETITION_ITEM, only_if_regulated=True),

    # Phase 3
    TaskTemplate("variables", Phase.DESIGN, "Fix variables and controls", "Independent, dependent and every controlled variable, written down.", 3, ["hypothesis"], Priority.HIGH),
    TaskTemplate("sample_size", Phase.DESIGN, "Decide sample size and trial count", "Justify the number against your time budget.", 2, ["variables"], Priority.HIGH),
    TaskTemplate("procedure", Phase.DESIGN, "Write the procedure", "Detailed enough that someone else could run it without asking you.", 4, ["sample_size"], Priority.HIGH),
    TaskTemplate("data_template", Phase.DESIGN, "Build the data collection table", "Design it around the statistical test you intend to run.", 2, ["procedure"]),

    # Phase 4
    TaskTemplate("pilot", Phase.EXPERIMENTATION, "Run a pilot test", "Two or three trials to find out what actually goes wrong.", 4, ["procedure", "sponsor_approval"], Priority.CRITICAL),
    TaskTemplate("fix_procedure", Phase.EXPERIMENTATION, "Fix what the pilot exposed", "Update the written procedure and note why it changed.", 2, ["pilot"]),
    TaskTemplate("main_trials", Phase.EXPERIMENTATION, "Run the main trials", "The bulk of your calendar time. Randomise run order.", 0, ["fix_procedure"], Priority.CRITICAL),
    TaskTemplate("notebook", Phase.EXPERIMENTATION, "Keep the research notebook current", "Dated entries as you go, not reconstructed afterwards.", 3, ["pilot"], Priority.HIGH),
    TaskTemplate("photos", Phase.EXPERIMENTATION, "Photograph the setup", "Before you dismantle anything.", 1, ["pilot"]),

    # Phase 5
    TaskTemplate("clean_data", Phase.ANALYSIS, "Clean and organise the data", "Document every exclusion and why.", 3, ["main_trials"], Priority.HIGH),
    TaskTemplate("statistics", Phase.ANALYSIS, "Run the statistics", "The test you chose during design, plus effect size.", 4, ["clean_data"], Priority.HIGH),
    TaskTemplate("graphs", Phase.ANALYSIS, "Make the figures", "The main figure decides your poster layout, so make it first.", 4, ["statistics"], Priority.HIGH),
    TaskTemplate("error_analysis", Phase.ANALYSIS, "Analyse error and confounds", "What could have produced this result besides your variable?", 3, ["statistics"]),
    TaskTemplate("more_trials_decision", Phase.ANALYSIS, "Decide whether more trials are needed", "Cheaper to decide now than after the poster is printed.", 1, ["statistics"], Priority.HIGH),

    # Phase 6
    TaskTemplate("abstract", Phase.WRITE_UP, "Write the abstract", "Usually has a hard word limit — check it.", 3, ["graphs"], Priority.HIGH, RequirementSource.UNVERIFIED_COMPETITION_ITEM),
    TaskTemplate("results_section", Phase.WRITE_UP, "Write the results section", "Numbers and figures; save interpretation for the discussion.", 3, ["graphs"]),
    TaskTemplate("conclusion", Phase.WRITE_UP, "Write the conclusion and limitations", "Answer your question directly, then say what you cannot conclude.", 3, ["results_section"]),
    TaskTemplate("bibliography", Phase.WRITE_UP, "Finish the bibliography", "Consistent format, every source you actually used.", 2, ["results_section"]),

    # Phase 7
    TaskTemplate("poster_layout", Phase.POSTER, "Choose the poster layout", "Pick the layout that fits your main figure.", 1, ["graphs"], Priority.HIGH),
    TaskTemplate("poster_text", Phase.POSTER, "Draft and cut the poster text", "Then cut it again. Length is the most common poster problem.", 5, ["conclusion", "poster_layout"]),
    TaskTemplate("poster_figures", Phase.POSTER, "Place figures and captions", "Main figure large, captions short and specific.", 3, ["poster_text"]),
    TaskTemplate("poster_final", Phase.POSTER, "Proofread and print", "Print earlier than you think you need to.", 3, ["poster_figures"], Priority.CRITICAL),

    # Phase 8
    TaskTemplate("pitch_30", Phase.INTERVIEW, "Prepare 30-second and 2-minute explanations", "In your own words, out loud, timed.", 3, ["conclusion"], Priority.HIGH),
    TaskTemplate("defend_method", Phase.INTERVIEW, "Practise defending your design choices", "Why this control, this sample size, these levels.", 3, ["pitch_30"], Priority.HIGH),
    TaskTemplate("mock_judging", Phase.INTERVIEW, "Complete a mock judging session", "The highest-value hour of preparation you can spend.", 2, ["defend_method"], Priority.CRITICAL),
    TaskTemplate("limitations_practice", Phase.INTERVIEW, "Practise limitations and future work answers", "Judges reward candour here more than students expect.", 2, ["mock_judging"]),

    # Phase 9
    TaskTemplate("forms_check", Phase.COMPETITION, "Final forms check", "Signed, dated, and with you on the day.", 1, ["poster_final"], Priority.CRITICAL, RequirementSource.UNVERIFIED_COMPETITION_ITEM),
    TaskTemplate("materials_check", Phase.COMPETITION, "Materials and backup files check", "Board, notebook, printed backups, device chargers.", 1, ["poster_final"], Priority.HIGH),
    TaskTemplate("rehearsal", Phase.COMPETITION, "Full rehearsal", "Standing up, at the board, to somebody who will interrupt.", 2, ["mock_judging", "poster_final"], Priority.HIGH),
]

PHASE_MIN_DAYS = {
    Phase.IDEA: 5,
    Phase.RULES: 7,
    Phase.DESIGN: 5,
    Phase.EXPERIMENTATION: 10,
    Phase.ANALYSIS: 5,
    Phase.WRITE_UP: 4,
    Phase.POSTER: 5,
    Phase.INTERVIEW: 4,
    Phase.COMPETITION: 2,
}

BUFFER_DAYS = 3


@dataclass
class GeneratedTask:
    template: TaskTemplate
    start_date: date
    due_date: date
    hours: float
    ai_note: str | None = None


def _experiment_hours(trials: int | None, minutes: int | None, teammates: int) -> float:
    if not trials or not minutes:
        return 12.0
    raw = trials * minutes / 60
    # Setup and teardown are never zero, and teammates help sub-linearly.
    return round(raw * 1.35 / max(1, 1 + 0.6 * teammates), 1)


def generate(
    signals: ProjectSignals,
    *,
    competition_date: date,
    today: date,
    hours_per_week: float,
    trials: int | None,
    minutes_per_trial: int | None,
    teammates: int,
    regulated: bool,
    already_experimenting: bool,
    school_deadline: date | None = None,
) -> tuple[list[GeneratedTask], list[TimelineWarning]]:
    warnings: list[TimelineWarning] = []
    templates = [t for t in TEMPLATES if not (t.only_if_regulated and not regulated)]

    exp_hours = _experiment_hours(trials, minutes_per_trial, teammates)
    for t in templates:
        if t.key == "main_trials":
            t.hours = exp_hours

    # ---- effort per phase ------------------------------------------------- #
    phase_hours: dict[Phase, float] = {}
    for t in templates:
        phase_hours[t.phase] = phase_hours.get(t.phase, 0) + t.hours

    total_hours = sum(phase_hours.values())
    end = (school_deadline or competition_date)
    days_available = (end - today).days
    weeks_available = max(0.1, days_available / 7)
    available_hours = hours_per_week * weeks_available

    # ---- convert effort to calendar days ---------------------------------- #
    hours_per_day = max(0.5, hours_per_week / 7)
    phase_days: dict[Phase, int] = {}
    for phase, hours in phase_hours.items():
        needed = max(PHASE_MIN_DAYS[phase], round(hours / hours_per_day))
        phase_days[phase] = needed

    if regulated:
        # Approval is calendar-bound, not effort-bound. It waits on other people.
        phase_days[Phase.RULES] = max(phase_days[Phase.RULES], 21)

    required_days = sum(phase_days.values()) + BUFFER_DAYS

    # ---- compression, honestly reported ----------------------------------- #
    if required_days > days_available:
        shortfall = required_days - days_available
        ratio = max(0.4, days_available / max(1, required_days))
        for phase in phase_days:
            phase_days[phase] = max(2, int(phase_days[phase] * ratio))
        warnings.append(TimelineWarning(
            severity="high",
            message=(
                f"A realistic schedule for this project needs about {required_days} days and you have "
                f"{days_available}. The plan below has been compressed by {shortfall} days, which is "
                "the definition of a high-risk schedule."
            ),
            recommendation=(
                "Cut scope now rather than later: reduce trial count, drop the second factor, or move "
                "to a simpler measurement. Compressed analysis and poster time is where projects lose "
                "the most points."
            ),
        ))

    if trials and minutes_per_trial:
        exp_days = phase_days[Phase.EXPERIMENTATION]
        if exp_hours > hours_per_day * exp_days:
            warnings.append(TimelineWarning(
                severity="high",
                message=(
                    f"Your stated {trials} trials at {minutes_per_trial} minutes each is about "
                    f"{exp_hours:.0f} hours of bench time, but the schedule only leaves {exp_days} days "
                    f"for experimentation at {hours_per_day:.1f} hours a day."
                ),
                recommendation=(
                    f"Either reduce to roughly {max(3, int(hours_per_day * exp_days * 60 / max(1, minutes_per_trial)))} "
                    "trials per condition, run trials in parallel, or start experimentation earlier."
                ),
            ))

    if total_hours > available_hours:
        warnings.append(TimelineWarning(
            severity="medium",
            message=(
                f"Total estimated effort is about {total_hours:.0f} hours; at {hours_per_week} hours a "
                f"week you have roughly {available_hours:.0f} hours before the fair."
            ),
            recommendation="Increase weekly hours, share work with a teammate, or reduce the design.",
        ))

    if regulated and not already_experimenting:
        warnings.append(TimelineWarning(
            severity="high",
            message=(
                "This project shows possible pre-approval triggers, so experimentation cannot be "
                "scheduled until review is complete."
            ),
            recommendation=(
                "Start the forms this week. Approval is the only task in the project whose duration "
                "you do not control."
            ),
        ))
    if already_experimenting and regulated:
        warnings.append(TimelineWarning(
            severity="high",
            message=(
                "You have indicated experimentation has already started on a project with possible "
                "approval triggers."
            ),
            recommendation=(
                "Stop and speak to your sponsor today. Work done before required approval is usually "
                "not eligible, and it is better to find out now."
            ),
        ))

    if days_available < 21:
        warnings.append(TimelineWarning(
            severity="high",
            message=f"Only {days_available} days remain before your deadline.",
            recommendation="Prioritise a complete small project over an incomplete ambitious one.",
        ))

    # ---- backward pass ----------------------------------------------------- #
    from app.models.enums import PHASE_ORDER

    phase_windows: dict[Phase, tuple[date, date]] = {}
    cursor = end - timedelta(days=BUFFER_DAYS)
    for phase in reversed(PHASE_ORDER):
        if phase not in phase_days:
            continue
        span = phase_days[phase]
        phase_end = cursor
        phase_start = phase_end - timedelta(days=span)
        phase_windows[phase] = (phase_start, phase_end)
        cursor = phase_start - timedelta(days=1)

    earliest = min(start for start, _ in phase_windows.values())
    if earliest < today:
        # Everything is already late. Shift forward so nothing is scheduled in
        # the past, clamp to the deadline, and keep every window at least one
        # day wide so start never overtakes due.
        shift = (today - earliest).days
        shifted: dict[Phase, tuple[date, date]] = {}
        for phase, (start, finish) in phase_windows.items():
            new_start = min(start + timedelta(days=shift), end)
            new_end = min(max(finish + timedelta(days=shift), new_start + timedelta(days=1)), end)
            shifted[phase] = (min(new_start, new_end), new_end)
        phase_windows = shifted
        warnings.append(TimelineWarning(
            severity="high",
            message=(
                "Even after compression this plan does not fit before your deadline, so late phases "
                "have been stacked against the fair date."
            ),
            recommendation=(
                "Treat the dates below as the latest possible, not a comfortable schedule. Reduce "
                "scope or find more hours per week."
            ),
        ))

    # ---- lay tasks inside their phase window ------------------------------- #
    tasks: list[GeneratedTask] = []
    for phase in PHASE_ORDER:
        if phase not in phase_windows:
            continue
        p_start, p_end = phase_windows[phase]
        in_phase = [t for t in templates if t.phase == phase]
        if not in_phase:
            continue
        span_days = max(1, (p_end - p_start).days)
        step = span_days / len(in_phase)
        for i, template in enumerate(in_phase):
            start = min(p_start + timedelta(days=int(i * step)), p_end)
            due = min(p_start + timedelta(days=int((i + 1) * step)), p_end)
            tasks.append(GeneratedTask(
                template=template,
                start_date=start,
                due_date=max(due, start),
                hours=template.hours,
                ai_note=_note_for(template, regulated, trials),
            ))

    return tasks, warnings


def _note_for(t: TaskTemplate, regulated: bool, trials: int | None) -> str | None:
    if t.key == "src_irb":
        return "Duration here depends on your reviewers, not on you. Submit early and chase politely."
    if t.key == "pilot":
        return "Almost every project changes its procedure after the pilot. Budget for that rather than being surprised."
    if t.key == "main_trials" and trials:
        return f"Estimated from your stated {trials} trials per condition. Update the estimate if that number changes."
    if t.key == "graphs":
        return "Make the main figure before designing the poster — the figure determines the layout, not the other way round."
    if t.key == "mock_judging":
        return "Interview is the single largest rubric category. Practising it once is worth more than a fourth poster revision."
    if t.key == "classify" and regulated:
        return "Your description triggered the rules screen. Treat this as blocking everything downstream."
    return None


def recompute_downstream(changed_field: str) -> list[str]:
    """Section 35: what has to be redone when the question or a variable changes."""
    impacts = {
        "research_question": ["hypothesis", "variables", "procedure", "data_template", "abstract", "poster_text"],
        "dependent_variable": ["hypothesis", "data_template", "statistics", "graphs", "procedure"],
        "independent_variable": ["variables", "procedure", "sample_size", "data_template", "graphs"],
        "control": ["procedure", "data_template", "statistics"],
        "sample_size": ["procedure", "statistics", "main_trials"],
    }
    return impacts.get(changed_field, [])
