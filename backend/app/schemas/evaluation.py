"""The structured contract between the application and whatever AI produces its
analysis.

Nothing in the app parses free prose from a model. Every provider — the
deterministic heuristic engine or a hosted LLM — must return objects that
validate against these schemas, so a bad or hallucinated response fails loudly
at the boundary instead of leaking into a student's project.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EvidenceBasis, NoveltyStatus


class Base(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="forbid")


# --------------------------------------------------------------------------- #
# Interview
# --------------------------------------------------------------------------- #


class InterviewQuestion(Base):
    key: str
    dimension: str
    text: str
    why_asked: str
    hint: str | None = None
    input_type: str = "text"
    options: list[str] = Field(default_factory=list)


class AnswerCritique(Base):
    """What the mentor thought of the last thing the student said."""

    question_key: str
    accepted: bool
    note: str
    follow_up: str | None = None


class InterviewStep(Base):
    questions: list[InterviewQuestion]
    critiques: list[AnswerCritique] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    ready_to_evaluate: bool
    coverage: dict[str, bool] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


class DimensionScore(Base):
    key: str
    label: str
    score: int = Field(ge=0, le=100)
    basis: EvidenceBasis
    summary: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    criteria: dict[str, int] = Field(default_factory=dict)


class RubricLine(Base):
    key: str
    label: str
    points_possible: int
    points_projected: int
    basis: EvidenceBasis
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    to_improve: list[str] = Field(default_factory=list)


class AzsefRubric(Base):
    lines: list[RubricLine]
    points_possible: int
    points_projected: int
    assessable_points: int
    disclaimer: str


class NoveltyAnalysis(Base):
    status: NoveltyStatus
    confidence: str
    headline: str
    similar_existing_ideas: list[str] = Field(default_factory=list)
    whats_different: list[str] = Field(default_factory=list)
    novelty_risks: list[str] = Field(default_factory=list)
    ways_to_increase: list[str] = Field(default_factory=list)
    literature_search_performed: bool = False
    sources: list[str] = Field(default_factory=list)
    evidence_note: str


class SafetyFlag(Base):
    category: str
    label: str
    matched_terms: list[str] = Field(default_factory=list)
    why_it_matters: str
    likely_paperwork: list[str] = Field(default_factory=list)


class SafetyScreening(Base):
    flags: list[SafetyFlag] = Field(default_factory=list)
    preapproval_possible: bool
    determination_made: bool = False
    notice: str


class EvaluationResult(Base):
    overall_score: int = Field(ge=0, le=100)
    information_completeness: int = Field(ge=0, le=100)
    dimensions: list[DimensionScore]
    rubric: AzsefRubric
    novelty: NoveltyAnalysis
    safety: SafetyScreening
    mentor_summary: str
    next_actions: list[str] = Field(default_factory=list)
    socratic_questions: list[str] = Field(default_factory=list)
    provider: str = "heuristic"


# --------------------------------------------------------------------------- #
# Refinement
# --------------------------------------------------------------------------- #


class QuestionVariant(Base):
    variant: str  # safe | competitive | ambitious
    label: str
    question: str
    independent_variable: str
    dependent_variable: str
    controls: list[str]
    population: str
    hypothesis: str
    primary_measurement: str
    experiment_type: str
    what_changed: list[str]
    trade_offs: list[str]


class RefinementResult(Base):
    original_question: str
    diagnosis: list[str]
    variants: list[QuestionVariant]
    note: str


# --------------------------------------------------------------------------- #
# Research plan
# --------------------------------------------------------------------------- #


class ResearchPlanDoc(Base):
    research_question: str
    background_problem: str
    purpose: str
    hypothesis: str
    independent_variable: str
    dependent_variable: str
    controlled_variables: list[str]
    experimental_group: str
    control_group: str
    materials: list[str]
    procedure: list[str]
    trials: str
    data_to_collect: list[str]
    suggested_graphs: list[str]
    statistical_analysis: list[str]
    sources_of_error: list[str]
    confounding_variables: list[str]
    safety_concerns: list[str]
    limitations: list[str]
    expected_contribution: str
    future_research: list[str]
    disclaimer: str


# --------------------------------------------------------------------------- #
# Poster + interview coaching
# --------------------------------------------------------------------------- #


class PosterSectionGuide(Base):
    key: str
    title: str
    purpose: str
    target_words: int
    currently_has: str
    should_add: list[str]
    should_remove: list[str]
    judge_questions: list[str]


class PosterLayout(Base):
    key: str
    name: str
    columns: dict[str, list[str]]
    why_it_fits: str
    fit_score: int = Field(ge=0, le=100)


class FigureSuggestion(Base):
    name: str
    kind: str
    why: str
    where_on_poster: str


class PosterPlan(Base):
    sections: list[PosterSectionGuide]
    layouts: list[PosterLayout]
    figures: list[FigureSuggestion]
    visual_assets: list[FigureSuggestion]


class PosterCritique(Base):
    score: int = Field(ge=0, le=100)
    basis: EvidenceBasis
    main_problems: list[str]
    text_length_flags: list[str]
    strengths: list[str]
    disclaimer: str


class JudgeQuestion(Base):
    category: str
    text: str
    what_theyre_probing: str
    difficulty: str


class InterviewPrepSet(Base):
    questions: list[JudgeQuestion]
    pitch_prompts: list[str]


class MockJudgeTurn(Base):
    role: str  # judge | student
    text: str


class MockJudgeReply(Base):
    judge_question: str
    reaction: str | None = None
    probing: str
    turn_index: int
    finished: bool = False


class MockJudgeReport(Base):
    readiness: int = Field(ge=0, le=100)
    strong_answers: list[str]
    weak_answers: list[str]
    concepts_to_review: list[str]
    struggled_with: list[str]
    communication_problems: list[str]
    better_explanations: list[str]
