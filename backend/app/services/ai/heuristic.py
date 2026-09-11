"""The default provider: deterministic, offline, auditable.

It composes the rule-based services rather than owning any scoring logic itself,
so the hosted provider and this one grade against the same definitions.
"""

from __future__ import annotations

from app.models.enums import Stage
from app.schemas.assistant import AssistantReply
from app.schemas.evaluation import (
    EvaluationResult,
    InterviewPrepSet,
    InterviewStep,
    MockJudgeReply,
    MockJudgeReport,
    PosterCritique,
    PosterPlan,
    RefinementResult,
    ResearchPlanDoc,
)
from app.services import interview_bank, judging, novelty, plan_builder, poster, refine, rubric, safety, scoring
from app.services.signals import ProjectSignals
from app.services.ai import assistant_heuristic


class HeuristicProvider:
    name = "heuristic"

    # -- interview ---------------------------------------------------------- #

    def next_questions(
        self, signals: ProjectSignals, max_questions: int = 3, newly_answered: list[str] | None = None
    ) -> InterviewStep:
        return interview_bank.build_step(signals, newly_answered or [], max_questions)

    # -- evaluation --------------------------------------------------------- #

    def evaluate(
        self,
        signals: ProjectSignals,
        stage: Stage = Stage.IDEA,
        has_poster_draft: bool = False,
        mock_interview_done: bool = False,
    ) -> EvaluationResult:
        screening = safety.screen(signals.any_text())
        nov = novelty.analyse(signals)

        dims = [
            scoring.research_question_quality(signals),
            scoring.methodology_potential(signals),
            scoring.creativity(signals, nov),
            scoring.feasibility(signals, len(screening.flags)),
            scoring.scientific_depth(signals),
        ]
        by_key = {d.key: d for d in dims}
        completeness = signals.completeness
        overall = scoring.overall(dims, completeness)

        return EvaluationResult(
            overall_score=overall,
            information_completeness=completeness,
            dimensions=dims,
            rubric=rubric.build(signals, by_key, stage, has_poster_draft, mock_interview_done),
            novelty=nov,
            safety=screening,
            mentor_summary=_summary(signals, by_key, overall, completeness, screening),
            next_actions=_next_actions(signals, by_key, screening),
            socratic_questions=_socratic(signals, by_key),
            provider=self.name,
        )

    # -- refinement and planning ------------------------------------------- #

    def refine(self, signals: ProjectSignals) -> RefinementResult:
        return refine.build(signals)

    def research_plan(self, signals: ProjectSignals, question: str) -> ResearchPlanDoc:
        return plan_builder.build(signals, question)

    # -- poster ------------------------------------------------------------- #

    def poster_plan(self, signals: ProjectSignals) -> PosterPlan:
        return poster.plan(signals)

    def poster_critique(self, signals: ProjectSignals, sections: dict[str, str]) -> PosterCritique:
        return poster.critique(signals, sections)

    # -- judging ------------------------------------------------------------ #

    def judge_questions(self, signals: ProjectSignals) -> InterviewPrepSet:
        return judging.prep_set(signals)

    def mock_judge_turn(
        self, signals: ProjectSignals, transcript: list[dict], answer: str | None
    ) -> MockJudgeReply:
        return judging.mock_turn(signals, transcript, answer)

    def mock_judge_report(self, signals: ProjectSignals, transcript: list[dict]) -> MockJudgeReport:
        return judging.mock_report(signals, transcript)


# --------------------------------------------------------------------------- #
# Narrative assembly
# --------------------------------------------------------------------------- #

    def assistant_reply(
        self,
        message: str,
        context: dict | None = None,
        history: list[dict] | None = None,
    ) -> AssistantReply:
        """Offline mentor. See app.services.ai.assistant_heuristic."""

        return assistant_heuristic.reply(message, context, history)



def _summary(signals, dims, overall, completeness, screening) -> str:
    weakest = min(dims.values(), key=lambda d: d.score)
    parts = [
        f"Readiness {overall}/100, based on {completeness}% of the information this tool needs.",
    ]
    if completeness < 60:
        parts.append(
            "That score is capped by missing answers rather than by the quality of the idea — "
            "finish the interview before reading too much into it."
        )
    parts.append(f"Weakest area is {weakest.label.lower()} at {weakest.score}. {weakest.summary}")

    if signals.question_analysis.vague_verbs and not signals.quantitative_outcome:
        parts.append(
            "The question as written is testable in principle but does not say what gets measured, "
            "which is the single change that would move the most points."
        )
    if screening.flags:
        parts.append(
            f"{len(screening.flags)} possible approval trigger(s) were flagged. Resolve those before "
            "you plan any experimentation dates."
        )
    return " ".join(parts)


def _next_actions(signals, dims, screening) -> list[str]:
    actions: list[str] = []
    if screening.flags:
        actions.append("Ask your sponsor this week which forms your project needs. Approval is the longest-lead item.")
    if not signals.control_defined:
        actions.append("Define your control condition. Nothing else in the design can be finalised first.")
    if not signals.quantitative_outcome:
        actions.append("Rewrite your outcome as a number with a unit and a measurement interval.")
    if not signals.literature_grounded:
        actions.append("Find three sources and record, for each, what they found and what they left open.")
    if not signals.mechanism_explained:
        actions.append("Write one paragraph explaining why you expect the effect, citing where you learned it.")
    if not signals.trial_count:
        actions.append("Work out the maximum number of trials your schedule allows, then justify the number.")
    if not actions:
        actions.append("Run a pilot trial. Everything above is settled enough that the next information comes from doing it.")
    return actions[:5]


def _socratic(signals, dims) -> list[str]:
    questions = [
        "What result would prove you wrong?",
        "How would you distinguish correlation from causation here?",
        "What would make this experiment fail entirely?",
    ]
    if not signals.mechanism_explained:
        questions.insert(0, "Why would that happen? Name the process, not the outcome.")
    if dims["creativity"].score < 50:
        questions.insert(0, "Why has this not already been settled by someone else?")
    if not signals.control_defined:
        questions.insert(0, "What would your control be?")
    return questions[:5]
