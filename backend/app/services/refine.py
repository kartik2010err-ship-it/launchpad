"""Question refinement (section 6).

The original is never overwritten. Three variants are offered along a single
axis — how much risk the student is taking on — and each one is fully
specified so the trade-off is concrete rather than rhetorical.
"""

from __future__ import annotations

from app.models.enums import ProjectType
from app.schemas.evaluation import QuestionVariant, RefinementResult
from app.services.signals import ProjectSignals, first_int, is_substantive

FALLBACK = {
    "iv": "the variable you are changing",
    "dv": "your measured outcome",
    "population": "your chosen system",
    "measurement": "a numeric measurement with a stated unit",
}


def _iv(s: ProjectSignals) -> str:
    if s.project_type == ProjectType.ENGINEERING:
        return s.get("alternatives") or s.get("constraints") or "your design alternatives"
    return s.get("independent_variable") or FALLBACK["iv"]


def _dv(s: ProjectSignals) -> str:
    if s.project_type == ProjectType.ENGINEERING:
        return s.get("comparison_metric") or s.get("success_metric") or FALLBACK["dv"]
    return s.get("dependent_variable") or FALLBACK["dv"]


def _population(s: ProjectSignals) -> str:
    if s.project_type == ProjectType.ENGINEERING:
        return s.get("who_experiences") or "your target use case"
    return s.get("population") or FALLBACK["population"]


def _measurement(s: ProjectSignals) -> str:
    return s.get("measurement") or s.get("success_metric") or FALLBACK["measurement"]


def _clip(text: str, n: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip(" ,.;") + "…"


def build(s: ProjectSignals) -> RefinementResult:
    iv, dv = _clip(_iv(s)), _clip(_dv(s))
    population, measurement = _clip(_population(s)), _clip(_measurement(s), 110)
    trials = s.trial_count or 10
    engineering = s.project_type == ProjectType.ENGINEERING

    diagnosis = list(s.question_analysis.issues)
    if not s.control_defined:
        diagnosis.append("No baseline is defined, so no version of this question is answerable yet.")
    if not s.differentiator_stated:
        diagnosis.append("Nothing yet distinguishes this from the standard version of the project.")
    if not diagnosis:
        diagnosis.append("The question is structurally sound; the variants below vary ambition, not correctness.")

    if engineering:
        variants = _engineering_variants(iv, dv, population, measurement, trials)
    else:
        variants = _scientific_variants(iv, dv, population, measurement, trials)

    return RefinementResult(
        original_question=s.question,
        diagnosis=diagnosis[:5],
        variants=variants,
        note=(
            "These are drafts to argue with, not answers. Pick the one you can defend in an "
            "interview and rewrite it in your own words — a question you cannot explain out loud "
            "will cost you more points than a simpler one you own."
        ),
    )


def _scientific_variants(iv, dv, population, measurement, trials) -> list[QuestionVariant]:
    return [
        QuestionVariant(
            variant="safe",
            label="Safe and feasible",
            question=(
                f"How does {iv}, tested at three defined levels, affect {dv} in {population}, "
                f"measured as {measurement}?"
            ),
            independent_variable=f"{iv}, at three fixed levels you choose in advance",
            dependent_variable=dv,
            controls=[
                f"An untreated {population} group held at your baseline level of {iv}",
                "All other conditions held constant and documented",
            ],
            population=population,
            hypothesis=f"{dv} will change monotonically as {iv} increases across the three levels.",
            primary_measurement=measurement,
            experiment_type="Single-factor comparison with a control group",
            what_changed=[
                "Fixed the number of levels so the design is countable.",
                "Named the population instead of a broad category.",
                "Moved the measurement into the question itself.",
            ],
            trade_offs=[
                f"Reliably completable with about {max(trials, 5)} trials per level.",
                "Low ceiling on creativity points — this is the standard shape of the project.",
            ],
        ),
        QuestionVariant(
            variant="competitive",
            label="Competitive",
            question=(
                f"How do {iv} and one interacting background condition jointly affect {dv} in "
                f"{population}, and does the effect of {iv} depend on that condition?"
            ),
            independent_variable=f"{iv} (3 levels) crossed with one background condition (2 levels)",
            dependent_variable=dv,
            controls=[
                "A cell at baseline for both factors",
                "Randomised assignment or randomised run order",
                "Every non-manipulated variable logged per trial",
            ],
            population=population,
            hypothesis=(
                f"The effect of {iv} on {dv} will be larger under one background condition than the "
                "other, producing an interaction rather than two independent effects."
            ),
            primary_measurement=measurement,
            experiment_type="Two-factor factorial design with interaction analysis",
            what_changed=[
                "Added a second factor so the project can report an interaction, not just an effect.",
                "Introduced randomisation, which judges look for specifically.",
                "Made the analysis two-way rather than a single comparison.",
            ],
            trade_offs=[
                f"Six cells instead of three: roughly double the trials ({max(trials, 5) * 6} total).",
                "Needs a two-way ANOVA or equivalent, so the analysis has to be learned in advance.",
            ],
        ),
        QuestionVariant(
            variant="ambitious",
            label="Ambitious and high-risk",
            question=(
                f"Which mechanism explains the effect of {iv} on {dv} in {population} — can the two "
                "candidate explanations be separated by measuring an intermediate variable over time?"
            ),
            independent_variable=f"{iv}, plus a manipulation that isolates one candidate mechanism",
            dependent_variable=f"{dv}, plus an intermediate variable measured repeatedly",
            controls=[
                "Baseline condition",
                "A condition that blocks one mechanism while leaving the other intact",
                "Repeated measures on the same units to track change over time",
            ],
            population=population,
            hypothesis=(
                "If mechanism A operates, the intermediate variable will move before the outcome does; "
                "if mechanism B operates, the two will move together."
            ),
            primary_measurement=f"{measurement}, plus a second instrumented measurement of the intermediate variable",
            experiment_type="Mechanism-discriminating design with repeated measures",
            what_changed=[
                "Shifted the question from 'does it happen' to 'why does it happen', which is where the top scores live.",
                "Added an intermediate measurement that can distinguish two explanations.",
                "Extended to repeated measures so timing carries information.",
            ],
            trade_offs=[
                "Needs an instrument or assay you may not have, and a pilot to prove it works.",
                "Realistic only with 8+ weeks and a mentor who knows the technique.",
                "High reward: this is the shape of a project that wins its category.",
            ],
        ),
    ]


def _engineering_variants(iv, dv, population, measurement, trials) -> list[QuestionVariant]:
    return [
        QuestionVariant(
            variant="safe",
            label="Safe and feasible",
            question=(
                f"Which of three design alternatives for {iv} achieves the best {dv} for {population}, "
                f"measured as {measurement}?"
            ),
            independent_variable="Three build variants differing in one design parameter",
            dependent_variable=dv,
            controls=["A benchmark build using the standard existing approach", "Identical test rig and conditions for every variant"],
            population=population,
            hypothesis=f"The variant optimised for {dv} will outperform the benchmark by a measurable margin.",
            primary_measurement=measurement,
            experiment_type="Comparative prototype testing against a benchmark",
            what_changed=[
                "Turned an open build into a comparison with a benchmark.",
                "Fixed the number of variants so testing is bounded.",
                "Named the decision metric.",
            ],
            trade_offs=[f"Achievable with {max(trials, 5)} test runs per variant.", "Limited novelty — comparative testing is the expected baseline."],
        ),
        QuestionVariant(
            variant="competitive",
            label="Competitive",
            question=(
                f"How does {dv} for {population} trade off against a second constraint across a "
                f"designed sweep of {iv}, and where is the optimum?"
            ),
            independent_variable=f"{iv} swept across a defined range, with a second constraint tracked",
            dependent_variable=f"{dv} and the competing constraint (cost, mass, power or time)",
            controls=["Benchmark existing solution measured on both axes", "Fixed test protocol across all runs"],
            population=population,
            hypothesis="Performance and the competing constraint will trade off non-linearly, producing an identifiable optimum rather than a monotonic gain.",
            primary_measurement=measurement,
            experiment_type="Parameter sweep with multi-objective trade-off analysis",
            what_changed=[
                "Introduced a real engineering trade-off instead of a single-objective 'better'.",
                "Swept a range rather than testing three points, so the result is a curve.",
                "Made the deliverable an optimum, which is a defensible finding.",
            ],
            trade_offs=["More builds and more test runs.", "Requires measuring two quantities reliably, not one."],
        ),
        QuestionVariant(
            variant="ambitious",
            label="Ambitious and high-risk",
            question=(
                f"Can an iteratively redesigned {iv} meet the stated requirements for {population} under "
                "a failure condition that defeats existing solutions, and what design principle explains why?"
            ),
            independent_variable="Successive prototype generations, each responding to a documented failure",
            dependent_variable=f"{dv} under both nominal and stress conditions",
            controls=["Existing commercial or published solution tested under the same stress condition", "Every generation retested under identical protocol"],
            population=population,
            hypothesis="A design change targeting the specific failure mode will hold performance under stress where the benchmark degrades.",
            primary_measurement=f"{measurement}, recorded under nominal and failure conditions",
            experiment_type="Iterative design cycle with stress testing and failure analysis",
            what_changed=[
                "Added a stress condition that existing solutions fail, which is where a genuine contribution lives.",
                "Made iteration the method rather than an accident.",
                "Requires explaining a design principle, not just reporting a winner.",
            ],
            trade_offs=[
                "Needs at least three build-test cycles; each takes longer than students estimate.",
                "Fails badly if the first prototype does not work — build in a fallback deliverable.",
            ],
        ),
    ]
