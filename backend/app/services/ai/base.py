"""The AI seam.

Everything above this line (routers, persistence, dashboards) talks only to
``ResearchAIProvider``. Everything below it is swappable. Two implementations
ship:

* ``HeuristicProvider`` — deterministic, offline, no API key. It is the default
  because a science-fair club should be able to run this on a school network in
  February with no budget, and because deterministic scores are reproducible
  when a mentor and a student are looking at the same project.
* ``AnthropicProvider`` — sends the same structured signals to a hosted model,
  validates the reply against the identical Pydantic schemas, and falls back to
  the heuristic result if validation fails.

Adding a third provider means implementing this protocol and registering it in
``factory.py``. Nothing else in the codebase changes.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

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
from app.services.signals import ProjectSignals


@runtime_checkable
class ResearchAIProvider(Protocol):
    name: str

    def next_questions(self, signals: ProjectSignals, max_questions: int = 3) -> InterviewStep:
        """Choose the most informative unanswered questions, and critique the last answers."""

    def evaluate(self, signals: ProjectSignals) -> EvaluationResult:
        """Score the project across all five dimensions plus rubric, novelty and safety."""

    def refine(self, signals: ProjectSignals) -> RefinementResult:
        """Produce safe / competitive / ambitious rewrites without discarding the original."""

    def research_plan(self, signals: ProjectSignals, question: str) -> ResearchPlanDoc:
        """Draft a starter research plan for the selected question."""

    def poster_plan(self, signals: ProjectSignals) -> PosterPlan:
        """Recommend poster structure, layouts and figures for this specific project."""

    def poster_critique(self, signals: ProjectSignals, sections: dict[str, str]) -> PosterCritique:
        """Coach the current poster text."""

    def judge_questions(self, signals: ProjectSignals) -> InterviewPrepSet:
        """Generate judge questions tailored to this project."""

    def mock_judge_turn(
        self, signals: ProjectSignals, transcript: list[dict], answer: str | None
    ) -> MockJudgeReply:
        """Advance a mock judging session by one exchange."""

    def mock_judge_report(self, signals: ProjectSignals, transcript: list[dict]) -> MockJudgeReport:
        """Summarise how the mock interview went."""

    def assistant_reply(
        self,
        message: str,
        context: dict | None = None,
        history: list[dict] | None = None,
    ) -> AssistantReply:
        """Answer one Research Assistant turn as a mentor, not as an answer key.

        ``context`` is the payload from ``app.services.assistant_context.build``:
        everything already on record about the project, or ``None`` for a chat
        opened outside one. ``history`` is prior turns as
        ``{"role": ..., "content": ...}``.

        Implementations must teach and challenge rather than produce the
        student's science for them (section 14), and must cite the Research
        Library by guide id rather than by URL (section 15).
        """
