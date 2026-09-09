"""Turn a project plus its interview transcript into structured, auditable signals.

Every score in the app is derived from this object rather than from a model's
opinion of the raw text. That has two benefits: the heuristic provider can score
offline and deterministically, and when a hosted LLM is doing the scoring the
same signals go into the prompt, so a student can always be told *which* piece
of missing information cost them points.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from app.models.enums import ProjectType

NON_ANSWERS = {
    "",
    "-",
    "n/a",
    "na",
    "none",
    "idk",
    "i dont know",
    "i don't know",
    "not sure",
    "no idea",
    "unsure",
    "tbd",
    "maybe",
    "?",
}

VAGUE_VERBS = (
    "affect",
    "impact",
    "influence",
    "change",
    "effect",
    "relate",
    "help",
    "improve",
    "better",
    "worse",
    "good",
    "bad",
)

BROAD_POPULATIONS = (
    "people",
    "humans",
    "students",
    "kids",
    "children",
    "adults",
    "plants",
    "animals",
    "bacteria",
    "everyone",
    "society",
    "the world",
)

UNIT_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s?"
    r"(?:%|percent|ms|milliseconds?|s|sec|seconds?|min|minutes?|h|hours?|days?|weeks?|"
    r"mm|cm|m|km|in|ft|mg|g|kg|lb|ml|l|°?c|°?f|celsius|fahrenheit|k|hz|bpm|db|"
    r"ppm|ppb|mol|molar|m/s|n|pa|kpa|w|kw|v|a|ohm|lux|px|fps|epochs?|trials?|samples?)\b",
    re.IGNORECASE,
)

NUMBER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\b")

MEASURABLE_VERBS = (
    "measure",
    "record",
    "count",
    "time",
    "weigh",
    "score",
    "log",
    "sample",
    "quantif",
    "accuracy",
    "rate",
    "concentration",
    "yield",
    "throughput",
    "latency",
    "error",
    "f1",
    "auc",
    "rmse",
    "percentage",
)

MECHANISM_WORDS = (
    "because",
    "since",
    "due to",
    "mechanism",
    "caused by",
    "explains",
    "theory",
    "principle",
    "law of",
    "reaction",
    "pathway",
    "receptor",
    "enzyme",
    "diffusion",
    "conduct",
    "absorb",
    "oxidat",
    "gradient",
    "resonance",
    "activation",
)

LITERATURE_WORDS = (
    "paper",
    "study",
    "studies",
    "journal",
    "article",
    "doi",
    "et al",
    "pubmed",
    "arxiv",
    "google scholar",
    "researcher",
    "published",
    "literature",
    "review",
)

RIGOUR_WORDS = (
    "replicate",
    "calibrat",
    "blank",
    "mass balance",
    "factorial",
    "crossed with",
    "interaction",
    "randomis",
    "randomiz",
    "blind",
    "held constant",
    "control for",
    "time series",
    "baseline",
    "standard",
)

STATS_WORDS = (
    "t-test",
    "t test",
    "anova",
    "chi-square",
    "chi square",
    "regression",
    "correlation",
    "p-value",
    "p value",
    "standard deviation",
    "confidence interval",
    "error bar",
    "significan",
    "mann-whitney",
    "cross-validation",
)


def normalise(text: str | None) -> str:
    return (text or "").strip()


def is_substantive(text: str | None, min_chars: int = 12) -> bool:
    """An answer counts only if the student actually said something."""
    value = normalise(text).lower().rstrip(".!")
    if value in NON_ANSWERS:
        return False
    if len(value) < min_chars:
        return False
    # "i don't know yet, maybe something" style deflections
    if re.match(r"^(i (dont|don't) know|not sure|no clue)\b", value) and len(value) < 40:
        return False
    return True


def contains_any(text: str | None, needles: Iterable[str]) -> list[str]:
    value = normalise(text).lower()
    return [n for n in needles if n in value]


def has_number(text: str | None) -> bool:
    return bool(NUMBER_PATTERN.search(normalise(text)))


def has_unit(text: str | None) -> bool:
    return bool(UNIT_PATTERN.search(normalise(text)))


def is_quantitative(text: str | None) -> bool:
    """A bare noun is not a measurement.

    "concentration" is a measurable quantity in chemistry and a mood in a
    behavioural project, so a measurement word only counts when it comes with a
    unit or with enough surrounding detail to show the student means a number.
    """
    value = normalise(text)
    if has_unit(value):
        return True
    return bool(contains_any(value, MEASURABLE_VERBS)) and len(value.split()) >= 4


def first_int(text: str | None) -> int | None:
    match = NUMBER_PATTERN.search(normalise(text))
    if not match:
        return None
    try:
        return int(float(match.group()))
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Question-level analysis
# --------------------------------------------------------------------------- #


@dataclass
class QuestionAnalysis:
    text: str
    word_count: int
    is_interrogative: bool
    vague_verbs: list[str]
    broad_populations: list[str]
    names_levels: bool
    names_measurement: bool
    has_comparison: bool
    names_population: bool

    @property
    def issues(self) -> list[str]:
        out: list[str] = []
        if self.vague_verbs and not self.names_measurement:
            out.append(
                f"Uses the open-ended verb \"{self.vague_verbs[0]}\" without saying what gets "
                "measured, so two people could test this question in completely different ways."
            )
        if self.broad_populations:
            out.append(
                f"\"{self.broad_populations[0]}\" is too broad to sample. Judges will ask which "
                "specific group, species, material or system you actually tested."
            )
        if not self.names_levels:
            out.append(
                "No specific levels or conditions are stated. Naming the exact values you will "
                "compare turns a topic into an experiment."
            )
        if not self.names_measurement:
            out.append("The outcome is not stated as something you can record as a number.")
        if self.word_count < 8:
            out.append("Too short to contain a variable, a population and an outcome.")
        if self.word_count > 45:
            out.append("Long enough that the actual question is hard to locate. Tighten it.")
        return out


def analyse_question(text: str) -> QuestionAnalysis:
    raw = normalise(text)
    lower = raw.lower()
    return QuestionAnalysis(
        text=raw,
        word_count=len(raw.split()),
        is_interrogative=raw.endswith("?")
        or lower.startswith(("how", "what", "which", "does", "do", "is", "are", "can", "to what")),
        vague_verbs=[v for v in VAGUE_VERBS if re.search(rf"\b{v}\w*\b", lower)],
        broad_populations=[p for p in BROAD_POPULATIONS if re.search(rf"\b{p}\b", lower)],
        names_levels=has_number(raw) or bool(re.search(r"\bversus\b|\bvs\.?\b|\bcompared (?:to|with)\b", lower)),
        names_measurement=bool(contains_any(lower, MEASURABLE_VERBS)) or has_unit(raw),
        has_comparison=bool(re.search(r"\bversus\b|\bvs\.?\b|\bcompared (?:to|with)\b|\bbetween\b", lower)),
        names_population=bool(re.search(r"\b(in|among|for|of)\s+\w+", lower)),
    )


# --------------------------------------------------------------------------- #
# Project-level signals
# --------------------------------------------------------------------------- #

SCIENTIFIC_KEYS = [
    "goal",
    "independent_variable",
    "dependent_variable",
    "measurement",
    "population",
    "prediction",
    "mechanism",
    "control",
    "trials",
    "resources",
    "time_budget",
    "regulated",
    "prior_work",
    "differentiator",
]

ENGINEERING_KEYS = [
    "problem",
    "who_experiences",
    "constraints",
    "existing_solutions",
    "existing_weaknesses",
    "success_metric",
    "alternatives",
    "prototype",
    "test_method",
    "comparison_metric",
    "resources",
    "time_budget",
    "regulated",
    "prior_work",
]


@dataclass
class ProjectSignals:
    project_type: ProjectType
    question: str
    question_analysis: QuestionAnalysis
    answers: dict[str, str] = field(default_factory=dict)
    topic: str = ""
    background_knowledge: str = ""
    category: str = ""
    grade_level: int = 9

    # ---- answer helpers -------------------------------------------------- #

    def get(self, key: str) -> str:
        return normalise(self.answers.get(key))

    def has(self, key: str) -> bool:
        return is_substantive(self.answers.get(key))

    def any_text(self) -> str:
        return " ".join(
            [self.question, self.topic, self.background_knowledge, *self.answers.values()]
        )

    # ---- derived facts --------------------------------------------------- #

    @property
    def required_keys(self) -> list[str]:
        return (
            ENGINEERING_KEYS
            if self.project_type == ProjectType.ENGINEERING
            else SCIENTIFIC_KEYS
        )

    @property
    def coverage(self) -> dict[str, bool]:
        return {key: self.has(key) for key in self.required_keys}

    @property
    def completeness(self) -> int:
        covered = sum(1 for v in self.coverage.values() if v)
        return round(100 * covered / max(1, len(self.required_keys)))

    @property
    def trial_count(self) -> int | None:
        return first_int(self.get("trials"))

    @property
    def quantitative_outcome(self) -> bool:
        target = " ".join(
            filter(None, [
                self.get("measurement"),
                self.get("dependent_variable"),
                self.get("comparison_metric"),
                self.get("success_metric"),
            ])
        )
        return is_quantitative(target)

    @property
    def mechanism_explained(self) -> bool:
        source = " ".join([self.get("mechanism"), self.get("prediction"), self.background_knowledge])
        return is_substantive(self.get("mechanism"), 25) and bool(
            contains_any(source, MECHANISM_WORDS)
        )

    @property
    def control_defined(self) -> bool:
        control = self.get("control") or self.get("test_method")
        return is_substantive(control, 15) and not control.lower().startswith("no ")

    @property
    def literature_grounded(self) -> bool:
        return is_substantive(self.get("prior_work"), 25) and bool(
            contains_any(self.get("prior_work"), LITERATURE_WORDS)
        )

    @property
    def differentiator_stated(self) -> bool:
        return is_substantive(self.get("differentiator") or self.get("existing_weaknesses"), 25)

    @property
    def stats_aware(self) -> bool:
        return bool(contains_any(self.any_text(), STATS_WORDS))

    @property
    def rigour_markers(self) -> list[str]:
        """Design-rigour vocabulary: replicates, blanks, calibration, factorial
        structure. Present in a description, these are strong evidence the
        student has thought past a single comparison."""
        return contains_any(self.any_text(), RIGOUR_WORDS)

    @property
    def factorial_design(self) -> bool:
        return bool(contains_any(self.any_text(), ("crossed with", "factorial", "interaction", "two factors")))

    @property
    def time_realistic(self) -> bool | None:
        """None when we simply do not know yet."""
        if not self.has("time_budget"):
            return None
        weeks = first_int(self.get("time_budget"))
        trials = self.trial_count
        if weeks is None:
            return None
        if trials and weeks <= 2 and trials > 20:
            return False
        return weeks >= 3


def build_signals(project, answers: dict[str, str]) -> ProjectSignals:
    return ProjectSignals(
        project_type=ProjectType(project.project_type),
        question=project.current_question,
        question_analysis=analyse_question(project.current_question),
        answers=answers,
        topic=normalise(project.topic),
        background_knowledge=normalise(project.background_knowledge),
        category=str(project.category),
        grade_level=project.grade_level,
    )
