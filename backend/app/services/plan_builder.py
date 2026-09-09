"""Research plan drafting (section 7).

A scaffold, not a submission. Every field is filled from what the student
actually told the interview; where they told us nothing, the plan says so out
loud instead of inventing a plausible-sounding procedure.
"""

from __future__ import annotations

from app.models.enums import ProjectType
from app.schemas.evaluation import ResearchPlanDoc
from app.services.safety import screen
from app.services.signals import ProjectSignals

MISSING = "— you have not answered this yet; fill it in before showing this plan to a sponsor."

DISCLAIMER = (
    "This is a planning aid generated from your own interview answers. It is not a research plan "
    "you can submit. Rewrite every section in your own words, check each procedure step against "
    "what you can actually do, and have your sponsor review it before you start."
)


def _or_missing(value: str, fallback: str | None = None) -> str:
    return value if value else (fallback or MISSING)


def build(s: ProjectSignals, question: str) -> ResearchPlanDoc:
    engineering = s.project_type == ProjectType.ENGINEERING
    safety = screen(s.any_text())
    trials = s.trial_count

    iv = _or_missing(s.get("independent_variable") or s.get("alternatives"))
    dv = _or_missing(s.get("dependent_variable") or s.get("comparison_metric") or s.get("success_metric"))
    population = _or_missing(s.get("population") or s.get("who_experiences"))
    measurement = _or_missing(s.get("measurement") or s.get("test_method"))

    graphs = _graph_suggestions(s)
    stats = _stat_suggestions(s, trials)

    procedure = _procedure(s, engineering, measurement, trials)

    return ResearchPlanDoc(
        research_question=question,
        background_problem=_or_missing(
            s.get("prior_work") or s.get("existing_solutions") or s.background_knowledge,
            "State what is already known and where the open question sits. " + MISSING,
        ),
        purpose=_or_missing(s.get("goal") or s.get("problem")),
        hypothesis=_or_missing(
            s.get("prediction"),
            "State a prediction specific enough to be wrong. " + MISSING,
        ),
        independent_variable=iv,
        dependent_variable=dv,
        controlled_variables=_controlled_variables(s),
        experimental_group=(
            f"Builds or conditions in which {iv} is varied"
            if engineering
            else f"{population} exposed to each non-baseline level of {iv}"
        ),
        control_group=_or_missing(
            s.get("control") or s.get("test_method"),
            "Define a condition identical in every respect except the variable you manipulate. " + MISSING,
        ),
        materials=_split_list(s.get("resources")) or [MISSING],
        procedure=procedure,
        trials=(
            f"{trials} per condition (stated by you)"
            if trials
            else "Not yet decided. Aim for at least 10 per condition and justify the number you land on."
        ),
        data_to_collect=[
            f"Primary outcome: {dv}",
            f"Measurement protocol: {measurement}",
            "Date, time and run order of every trial",
            "Every deviation from the written procedure, with the reason",
            "Ambient conditions you are not controlling but could confound the result",
        ],
        suggested_graphs=graphs,
        statistical_analysis=stats,
        sources_of_error=[
            "Instrument resolution and calibration drift",
            "Operator variation between trials — decide now whether one person does all measurements",
            "Order effects if trials are run in sequence rather than randomised",
            "Loss of samples or failed runs, and how you will record rather than silently drop them",
        ],
        confounding_variables=_confounders(s),
        safety_concerns=(
            [f"{f.label}: {f.why_it_matters}" for f in safety.flags]
            or ["No obvious hazards identified from your description. Confirm with your sponsor anyway."]
        ),
        limitations=[
            "Sample size limits how small an effect you can detect.",
            "Results apply only to the specific system and conditions you tested.",
            "Any variable you did not control is a limitation, whether or not it affected the result.",
        ],
        expected_contribution=_or_missing(
            s.get("differentiator") or s.get("existing_weaknesses"),
            "State plainly what someone would know after your project that they did not know before. " + MISSING,
        ),
        future_research=[
            "The obvious next level or condition you could not fit in this year.",
            "A second measurement that would discriminate between competing explanations.",
            "Replication in a different population, material or setting.",
        ],
        disclaimer=DISCLAIMER,
    )


def _split_list(text: str) -> list[str]:
    if not text:
        return []
    parts = [p.strip(" .") for chunk in text.split("\n") for p in chunk.split(",")]
    return [p for p in parts if p][:12]


def _controlled_variables(s: ProjectSignals) -> list[str]:
    base = [
        "Everything not named as your independent variable — list them explicitly",
        "Measurement instrument and technique, kept identical across all trials",
        "Timing: same interval between treatment and measurement for every unit",
    ]
    if s.category in ("biomedical_science", "environmental_science"):
        base.append("Temperature, light and humidity of the growing or holding environment")
    if s.category == "computer_science":
        base.append("Random seed, hardware and software versions, and train/test split")
    return base


def _graph_suggestions(s: ProjectSignals) -> list[str]:
    iv_numeric = any(c.isdigit() for c in s.get("independent_variable"))
    out = []
    if iv_numeric:
        out.append("Scatter plot of outcome against your independent variable, with a fitted trend line")
    out.append("Bar chart of mean outcome per condition with error bars showing standard deviation")
    out.append("Box plot per condition to show spread, not just the mean — judges notice this")
    if s.category == "computer_science":
        out.append("Confusion matrix or ROC curve if your outcome is a classification")
    out.append("Raw-data table in an appendix, so the graphs can be checked against it")
    return out


def _stat_suggestions(s: ProjectSignals, trials: int | None) -> list[str]:
    out = ["Mean and standard deviation per condition, reported with the sample size"]
    if trials and trials >= 5:
        out.append("Two-sample t-test if you compare two conditions; one-way ANOVA for three or more")
    else:
        out.append(
            "With fewer than 5 trials per condition, report descriptive statistics honestly and avoid "
            "significance claims your sample cannot support"
        )
    out.append("Effect size alongside any p-value — 'significant' and 'large' are not the same claim")
    if any(c.isdigit() for c in s.get("independent_variable")):
        out.append("Linear regression with R² if your independent variable is continuous")
    return out


def _confounders(s: ProjectSignals) -> list[str]:
    generic = [
        "Selection effects: how units were assigned to conditions",
        "Time: anything that changes over the course of your data collection",
        "Measurement bias: knowing which condition you are measuring can shift how you read an instrument",
    ]
    if s.project_type == ProjectType.SCIENTIFIC and "human" in s.any_text().lower():
        generic.append("Practice and expectancy effects if the same person is tested more than once")
    return generic


def _procedure(s: ProjectSignals, engineering: bool, measurement: str, trials: int | None) -> list[str]:
    n = trials or 10
    if engineering:
        return [
            "Write down the measurable requirements your design must meet, with thresholds.",
            "Build or obtain the benchmark you will compare against.",
            "Build prototype variant 1, photographing each stage.",
            f"Test the benchmark and variant 1 under an identical protocol, {n} runs each.",
            f"Record {measurement} for every run, plus any failure and its cause.",
            "Analyse where variant 1 fell short, and change exactly one thing in response.",
            "Build and test variant 2, then variant 3, keeping the protocol fixed.",
            "Compare all variants against the benchmark on your decision metric.",
            "Document every design change and the evidence that motivated it.",
        ]
    return [
        "Write out the full procedure and have your sponsor read it before you touch anything.",
        "Run 2-3 pilot trials to find out what actually goes wrong. Expect to change the procedure here.",
        "Prepare all units and assign them to conditions randomly, recording the assignment.",
        "Set up the control condition first so you know your baseline reading is stable.",
        f"Run {n} trials per condition, randomising run order rather than doing all of one condition first.",
        f"Measure the outcome using this protocol every time: {measurement}",
        "Record raw values in your notebook at the moment of measurement, not afterwards.",
        "Log any deviation, failed run or unusual observation with the date and time.",
        "Repeat the control condition at the end to check nothing drifted.",
    ]
