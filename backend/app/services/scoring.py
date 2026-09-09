"""Research readiness scoring (section 3).

Each dimension is built from named sub-criteria scored 0-100, so a student can
always trace a number back to a specific missing or weak answer. The engine is
deliberately harsh in one direction: absent information scores low rather than
neutral, because a project that has not answered "what is your control" is not
in the same position as one that has.
"""

from __future__ import annotations

from statistics import mean

from app.models.enums import EvidenceBasis, NoveltyStatus, ProjectType
from app.schemas.evaluation import DimensionScore, NoveltyAnalysis
from app.services.novelty import NOVELTY_SCORE_MAP
from app.services.signals import (
    RIGOUR_WORDS,
    STATS_WORDS,
    ProjectSignals,
    contains_any,
    first_int,
    has_number,
    has_unit,
    is_substantive,
)


def _band(value: bool, high: int = 85, low: int = 25) -> int:
    return high if value else low


def _avg(values: dict[str, int]) -> int:
    return round(mean(values.values())) if values else 0


# --------------------------------------------------------------------------- #
# 1. Research question quality
# --------------------------------------------------------------------------- #


def research_question_quality(s: ProjectSignals) -> DimensionScore:
    qa = s.question_analysis
    iv_key = "independent_variable" if s.project_type == ProjectType.SCIENTIFIC else "constraints"
    dv_key = "dependent_variable" if s.project_type == ProjectType.SCIENTIFIC else "comparison_metric"

    criteria = {
        "clarity": 80 if qa.is_interrogative and 8 <= qa.word_count <= 40 else 45,
        "specificity": _band(qa.names_levels and not qa.broad_populations, 88, 30),
        "testability": _band(s.has(iv_key) and s.control_defined, 88, 35),
        "measurability": _band(s.quantitative_outcome, 90, 25),
        "scope": _band(bool(s.trial_count) and not qa.broad_populations, 80, 40),
        "variables_defined": _band(s.has(iv_key) and s.has(dv_key), 90, 25),
        "significance": _band(s.literature_grounded or s.differentiator_stated, 78, 38),
    }
    if qa.vague_verbs and not qa.names_measurement:
        criteria["clarity"] = min(criteria["clarity"], 50)

    strengths, weaknesses, improvements = [], [], []
    if criteria["measurability"] >= 80:
        strengths.append("The outcome is stated as something you can record as a number.")
    if criteria["variables_defined"] >= 80:
        strengths.append("Both variables are named, so the experiment has a shape.")
    if qa.names_levels:
        strengths.append("Specific levels or comparison conditions appear in the question.")

    weaknesses.extend(qa.issues)
    if not s.has(dv_key):
        weaknesses.append("No outcome variable has been given, so the question is not yet testable.")
    if not s.quantitative_outcome:
        weaknesses.append("The outcome is described qualitatively and cannot be graphed as written.")

    if not qa.names_levels:
        improvements.append("Name the exact conditions you will compare, including their values.")
    if qa.broad_populations:
        improvements.append(
            f"Replace \"{qa.broad_populations[0]}\" with the specific group, species or system you can access."
        )
    if not s.quantitative_outcome:
        improvements.append("Rewrite the outcome as a measurement with a unit and an interval.")
    if not improvements:
        improvements.append("Tighten wording until the question states variable, population and measurement in one line.")

    score = _avg(criteria)
    return DimensionScore(
        key="research_question",
        label="Research question quality",
        score=score,
        basis=EvidenceBasis.CURRENT_EVIDENCE,
        summary=_summary_for(score, "question"),
        strengths=strengths or ["Nothing to credit yet beyond having picked a topic."],
        weaknesses=weaknesses[:5] or ["No structural problems detected in the wording."],
        improvements=improvements[:4],
        criteria=criteria,
    )


# --------------------------------------------------------------------------- #
# 2. Methodology potential
# --------------------------------------------------------------------------- #


def methodology_potential(s: ProjectSignals) -> DimensionScore:
    trials = s.trial_count or 0
    if trials >= 15:
        sample = 90
    elif trials >= 10:
        sample = 80
    elif trials >= 5:
        sample = 62
    elif trials >= 3:
        sample = 42
    elif trials > 0:
        sample = 25
    else:
        sample = 20

    method_text = s.get("measurement") or s.get("test_method")
    rigour = len(s.rigour_markers)
    if s.factorial_design:
        # A crossed design multiplies the information a fixed trial budget buys.
        sample = min(95, sample + 12)
    criteria = {
        "answers_the_question": _band(s.has("measurement") or s.has("test_method"), 82, 30),
        "controls": _band(s.control_defined, 90, 20),
        "quantitative_data": _band(s.quantitative_outcome, 88, 25),
        "sample_size": sample,
        "reproducibility": min(95, _band(is_substantive(method_text, 40) and has_unit(method_text), 82, 35) + 3 * rigour),
        "confound_awareness": _band(
            is_substantive(s.get("control"), 30) or rigour >= 2,
            80, 30,
        ),
        "design_structure": 88 if s.factorial_design else (66 if rigour >= 2 else 38),
    }

    strengths, weaknesses, improvements = [], [], []
    if criteria["controls"] >= 80:
        strengths.append("A baseline condition is defined, so differences can be attributed.")
    if sample >= 62:
        strengths.append(f"{trials} trials per condition is enough to look for a real difference.")
    if criteria["reproducibility"] >= 80:
        strengths.append("The procedure is specific enough that someone else could repeat it.")
    if s.factorial_design:
        strengths.append("A crossed design lets you report an interaction, not just two separate effects.")
    if rigour >= 3:
        strengths.append(
            "Design vocabulary shows real rigour: " + ", ".join(s.rigour_markers[:4]) + "."
        )

    if not s.control_defined:
        weaknesses.append("No control or baseline. This alone caps how far the project can score.")
    if trials == 0:
        weaknesses.append("Sample size is unknown, so nothing can be said about statistical power.")
    elif trials < 5:
        weaknesses.append(f"{trials} trials per condition is very likely to be swamped by variability.")
    if not has_unit(method_text):
        weaknesses.append("The measurement protocol lacks units or intervals, which hurts reproducibility.")
    if criteria["confound_awareness"] < 50:
        weaknesses.append("No variables are named as held constant, so alternative explanations remain open.")

    if not s.control_defined:
        improvements.append("Define a condition identical to your experimental group except for the variable you change.")
    if trials < 10:
        improvements.append("Work out the maximum trials your time budget allows and aim for at least 10 per condition.")
    improvements.append("List every variable you will hold constant and how you will hold it constant.")
    if not s.stats_aware:
        improvements.append("Decide now which statistical test fits your data type — it constrains how you collect data.")

    score = _avg(criteria)
    basis = EvidenceBasis.CURRENT_EVIDENCE if s.has("measurement") or s.has("test_method") else EvidenceBasis.PROJECTED_POTENTIAL
    return DimensionScore(
        key="methodology",
        label="Methodology potential",
        score=score,
        basis=basis,
        summary=_summary_for(score, "methodology"),
        strengths=strengths or ["No methodology strengths are evidenced yet."],
        weaknesses=weaknesses[:5] or ["No methodological gaps detected in what you have described."],
        improvements=improvements[:4],
        criteria=criteria,
    )


# --------------------------------------------------------------------------- #
# 3. Creativity / originality
# --------------------------------------------------------------------------- #


def creativity(s: ProjectSignals, nov: NoveltyAnalysis) -> DimensionScore:
    base = NOVELTY_SCORE_MAP[NoveltyStatus(nov.status)]
    criteria = {
        "not_a_common_archetype": base,
        "articulated_difference": _band(s.differentiator_stated, 82, 28),
        "research_gap": _band(s.literature_grounded and s.differentiator_stated, 80, 32),
        "useful_new_information": _band(
            s.differentiator_stated and s.quantitative_outcome, 78, 35
        ),
    }
    score = _avg(criteria)

    weaknesses = list(nov.novelty_risks)
    if not s.literature_grounded:
        weaknesses.append("No sources cited, so any originality claim is currently unsupported.")

    return DimensionScore(
        key="creativity",
        label="Creativity and originality",
        score=score,
        basis=EvidenceBasis.CURRENT_EVIDENCE,
        summary=nov.headline,
        strengths=nov.whats_different[:3],
        weaknesses=weaknesses[:4],
        improvements=nov.ways_to_increase[:4],
        criteria=criteria,
    )


# --------------------------------------------------------------------------- #
# 4. Feasibility
# --------------------------------------------------------------------------- #


def feasibility(s: ProjectSignals, safety_flag_count: int) -> DimensionScore:
    weeks = first_int(s.get("time_budget"))
    trials = s.trial_count or 0
    resources_known = s.has("resources")
    access_stated = bool(contains_any(s.get("resources"), ("have", "access", "school", "own", "borrow", "free", "library", "lab")))

    if weeks is None:
        time_score = 40
    elif weeks >= 8:
        time_score = 85
    elif weeks >= 4:
        time_score = 65
    else:
        time_score = 35

    criteria = {
        "time": time_score,
        "cost": _band(bool(contains_any(s.get("resources"), ("cheap", "free", "under", "$", "household", "own"))), 80, 50),
        "equipment_access": _band(resources_known and access_stated, 85, 40),
        "expertise": _band(s.mechanism_explained or s.literature_grounded, 75, 45),
        "data_availability": _band(s.has("resources") or s.has("population"), 75, 45),
        "complexity": _band(trials and trials <= 60, 78, 45),
        "safety_and_approvals": max(20, 90 - 18 * safety_flag_count),
    }

    strengths, weaknesses, improvements = [], [], []
    if time_score >= 65:
        strengths.append("The stated time window leaves room for a pilot and a real run.")
    if criteria["equipment_access"] >= 80:
        strengths.append("You have named the materials and where they come from.")
    if safety_flag_count == 0:
        strengths.append("No obvious regulatory triggers appeared in the screening.")

    if weeks is not None and weeks < 4:
        weaknesses.append(f"{weeks} weeks is tight for design, pilot, trials and analysis.")
    if trials and weeks and trials * 0.5 > weeks * 5:
        weaknesses.append("Trial count looks large relative to the time available.")
    if not resources_known:
        weaknesses.append("Materials and access have not been confirmed, which is the usual point of failure.")
    if safety_flag_count:
        weaknesses.append(
            f"{safety_flag_count} possible approval trigger(s) detected — approval time must be built into the schedule."
        )

    if not resources_known:
        improvements.append("List every item you need and mark each as 'have', 'can borrow' or 'must buy'.")
    improvements.append("Run one pilot trial before committing to the full design. It always changes something.")
    if safety_flag_count:
        improvements.append("Ask your sponsor this week which forms apply. Approval is the slowest step in the project.")

    score = _avg(criteria)
    return DimensionScore(
        key="feasibility",
        label="Feasibility",
        score=score,
        basis=EvidenceBasis.PROJECTED_POTENTIAL,
        summary=_summary_for(score, "feasibility"),
        strengths=strengths or ["Not enough logistical detail to credit anything yet."],
        weaknesses=weaknesses[:5] or ["No feasibility blockers identified from what you have described."],
        improvements=improvements[:4],
        criteria=criteria,
    )


# --------------------------------------------------------------------------- #
# 5. Scientific depth
# --------------------------------------------------------------------------- #


def scientific_depth(s: ProjectSignals) -> DimensionScore:
    competing = bool(contains_any(s.any_text(), (
        "alternative explanation", "another explanation", "could also be", "rule out", "confound",
        "competing hypothes", "distinguish between", "interaction", "bypass", "blank",
    )))
    rigour = len(s.rigour_markers)
    criteria = {
        "mechanism_understood": _band(s.mechanism_explained, 88, 25),
        "beyond_demonstration": _band(s.differentiator_stated and s.quantitative_outcome, 78, 35),
        "competing_hypotheses": _band(competing, 82, 30),
        "analysis_potential": _band(s.stats_aware, 80, 38) if s.stats_aware else (58 if rigour >= 3 else 38),
    }

    strengths, weaknesses, improvements = [], [], []
    if s.mechanism_explained:
        strengths.append("You can state why the effect should happen, not only that it should.")
    if competing:
        strengths.append("You have considered at least one alternative explanation.")
    if s.stats_aware:
        strengths.append("A statistical approach is already in mind.")

    if not s.mechanism_explained:
        weaknesses.append("The mechanism behind the predicted effect is not explained. Judges open with this.")
    if not competing:
        weaknesses.append("No alternative explanation has been considered, so a confound could go unnoticed.")
    if not s.stats_aware:
        weaknesses.append("No analysis plan, which usually means the data get collected in an unanalysable shape.")

    improvements.append("Write one paragraph on the mechanism and cite where you learned it.")
    improvements.append("Name one alternative explanation for your predicted result and design a way to rule it out.")
    if not s.stats_aware:
        improvements.append("Pick your statistical test before collecting data, then design the table to fit it.")

    score = _avg(criteria)
    basis = EvidenceBasis.CURRENT_EVIDENCE if s.has("mechanism") or s.has("prior_work") else EvidenceBasis.NOT_YET_ASSESSABLE
    return DimensionScore(
        key="scientific_depth",
        label="Scientific depth",
        score=score,
        basis=basis,
        summary=_summary_for(score, "depth"),
        strengths=strengths or ["Depth is not yet evidenced — answer the mechanism question."],
        weaknesses=weaknesses[:4],
        improvements=improvements[:4],
        criteria=criteria,
    )


# --------------------------------------------------------------------------- #
# Aggregate
# --------------------------------------------------------------------------- #

WEIGHTS = {
    "research_question": 0.25,
    "methodology": 0.25,
    "creativity": 0.20,
    "feasibility": 0.15,
    "scientific_depth": 0.15,
}


def overall(dimensions: list[DimensionScore], completeness: int) -> int:
    raw = sum(d.score * WEIGHTS[d.key] for d in dimensions)
    # An incomplete interview cannot produce a high readiness score. Missing
    # information is treated as risk, not as neutral.
    ceiling = 55 + (completeness * 0.45)
    return int(min(raw, ceiling))


def _summary_for(score: int, kind: str) -> str:
    texts = {
        "question": [
            "This is still a topic rather than a research question.",
            "Recognisable as a question, but too loose to run an experiment from.",
            "A workable question with specific gaps to close.",
            "A well-formed question that a judge could engage with directly.",
        ],
        "methodology": [
            "There is not yet a method here, only an intention.",
            "The outline of a method exists but key controls or measurements are missing.",
            "A defensible method with identifiable weak points.",
            "A solid design that could withstand methodology questioning.",
        ],
        "feasibility": [
            "Too little logistical detail to judge whether this can be done.",
            "Serious feasibility risks in time, access or approvals.",
            "Achievable, with a few things to lock down.",
            "Realistic and well scoped for the time available.",
        ],
        "depth": [
            "The project currently describes an effect without explaining it.",
            "Some understanding of the underlying science, not yet enough to defend.",
            "Good grasp of mechanism with room to consider alternatives.",
            "Strong conceptual grounding that supports real analysis.",
        ],
    }
    band = 0 if score < 40 else 1 if score < 60 else 2 if score < 78 else 3
    return texts[kind][band]
