"""Hosted-model provider.

Design notes worth knowing before editing this file:

* The model is never asked to invent scores from raw prose. It receives the same
  ``ProjectSignals`` the heuristic engine uses, plus the heuristic result as a
  reference point, and is asked to produce a better-reasoned version of the same
  structure. That keeps the two providers comparable.
* Output is parsed into the Pydantic schemas. A response that fails validation is
  discarded and the heuristic result is returned instead — a student never sees a
  half-parsed evaluation.
* The prompt forbids inventing citations. If we ever add a real search tool, the
  ``sources`` field gets populated from it, not from the model's memory.
"""

from __future__ import annotations

import json
import logging

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.models.enums import Stage
from app.schemas.assistant import AssistantReply
from app.schemas.evaluation import (
    EvaluationResult,
    InterviewStep,
    RefinementResult,
    ResearchPlanDoc,
)
from app.services.ai import assistant_heuristic
from app.services.ai.heuristic import HeuristicProvider
from app.services.ai.prompts import (
    ASSISTANT_SYSTEM_PROMPT,
    EVALUATION_INSTRUCTION,
    INTERVIEW_INSTRUCTION,
    PLAN_INSTRUCTION,
    REFINE_INSTRUCTION,
    SYSTEM_PROMPT,
    signals_payload,
)
from app.services.signals import ProjectSignals

log = logging.getLogger(__name__)


class AnthropicProvider(HeuristicProvider):
    """Falls back to every heuristic method it does not override."""

    name = "anthropic"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.settings = get_settings()
        self._client = client or httpx.Client(timeout=60.0)

    # -- transport ---------------------------------------------------------- #

    def _call(self, instruction: str, payload: dict) -> dict | None:
        if not self.settings.anthropic_api_key:
            log.warning("anthropic provider selected but no API key configured; using heuristic output")
            return None
        body = {
            "model": self.settings.anthropic_model,
            "max_tokens": 4096,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": f"{instruction}\n\nPROJECT SIGNALS:\n{json.dumps(payload, indent=2)}",
                }
            ],
        }
        try:
            response = self._client.post(
                self.settings.anthropic_base_url,
                json=body,
                headers={
                    "x-api-key": self.settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
        except Exception:  # noqa: BLE001 - degrade to heuristic on any transport failure
            log.exception("AI call failed; falling back to heuristic scoring")
            return None

        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        return _parse_json(text)

    def _validated(self, model: type[BaseModel], raw: dict | None):
        if raw is None:
            return None
        try:
            return model.model_validate(raw)
        except ValidationError:
            log.exception("AI response failed schema validation; falling back to heuristic scoring")
            return None

    # -- overrides ---------------------------------------------------------- #

    def next_questions(self, signals: ProjectSignals, max_questions: int = 3, newly_answered=None) -> InterviewStep:
        fallback = super().next_questions(signals, max_questions, newly_answered)
        payload = signals_payload(signals) | {
            "max_questions": max_questions,
            "already_asked": list(signals.answers.keys()),
            "heuristic_step": fallback.model_dump(),
        }
        result = self._validated(InterviewStep, self._call(INTERVIEW_INSTRUCTION, payload))
        return result or fallback

    def evaluate(
        self,
        signals: ProjectSignals,
        stage: Stage = Stage.IDEA,
        has_poster_draft: bool = False,
        mock_interview_done: bool = False,
    ) -> EvaluationResult:
        fallback = super().evaluate(signals, stage, has_poster_draft, mock_interview_done)
        payload = signals_payload(signals) | {
            "stage": str(stage),
            "heuristic_evaluation": fallback.model_dump(),
        }
        result = self._validated(EvaluationResult, self._call(EVALUATION_INSTRUCTION, payload))
        if result is None:
            return fallback
        # The safety screen is rule-based and is never delegated to a model.
        result.safety = fallback.safety
        # A model cannot claim a literature search the app did not perform.
        result.novelty.literature_search_performed = fallback.novelty.literature_search_performed
        result.novelty.sources = fallback.novelty.sources
        result.provider = self.name
        return result

    def refine(self, signals: ProjectSignals) -> RefinementResult:
        fallback = super().refine(signals)
        payload = signals_payload(signals) | {"heuristic_variants": fallback.model_dump()}
        return self._validated(RefinementResult, self._call(REFINE_INSTRUCTION, payload)) or fallback

    def research_plan(self, signals: ProjectSignals, question: str) -> ResearchPlanDoc:
        fallback = super().research_plan(signals, question)
        payload = signals_payload(signals) | {
            "selected_question": question,
            "heuristic_plan": fallback.model_dump(),
        }
        return self._validated(ResearchPlanDoc, self._call(PLAN_INSTRUCTION, payload)) or fallback


def _parse_json(text: str) -> dict | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        log.warning("AI response was not valid JSON")
        return None


# --------------------------------------------------------------------------- #
# Research Assistant
# --------------------------------------------------------------------------- #


def _assistant_reply_impl(
    self,
    message: str,
    context: dict | None = None,
    history: list[dict] | None = None,
) -> AssistantReply:
    """Multi-turn chat. Falls back to the offline mentor on any failure.

    Unlike the scoring calls this one is a real conversation, so the transport
    differs: prior turns are replayed as messages and the project context is
    pinned to the front of the first user turn rather than appended to an
    instruction.
    """

    fallback = assistant_heuristic.reply(message, context, history)
    if not self.settings.anthropic_api_key:
        log.warning("anthropic provider selected but no API key configured; using offline assistant")
        return fallback

    turns: list[dict] = []
    for turn in (history or [])[-12:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            turns.append({"role": role, "content": content})

    opening = message
    if context:
        opening = (
            "PROJECT CONTEXT (what the app already knows — do not ask the student to repeat it):\n"
            f"{json.dumps(context, indent=2, default=str)}\n\n"
            f"STUDENT MESSAGE:\n{message}"
        )
    else:
        opening = (
            "No project is attached to this conversation, so you have no project context.\n\n"
            f"STUDENT MESSAGE:\n{message}"
        )

    # Context rides on the latest user turn, so it stays current as the thread grows.
    turns.append({"role": "user", "content": opening})

    body = {
        "model": self.settings.anthropic_model,
        "max_tokens": 1600,
        "system": ASSISTANT_SYSTEM_PROMPT,
        "messages": turns,
    }
    try:
        response = self._client.post(
            self.settings.anthropic_base_url,
            json=body,
            headers={
                "x-api-key": self.settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()
    except Exception:  # noqa: BLE001 — degrade to the offline mentor on any failure
        log.exception("assistant call failed; falling back to the offline assistant")
        return fallback

    text = "".join(
        block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
    )
    raw = _parse_json(text)
    if raw is None:
        # A well-formed prose answer is still worth showing; only the structure was lost.
        cleaned = text.strip()
        if cleaned:
            return AssistantReply(reply=cleaned, follow_ups=[], guide_ids=[])
        return fallback
    try:
        return AssistantReply.model_validate(raw)
    except ValidationError:
        log.warning("assistant reply failed validation; falling back to the offline assistant")
        return fallback


AnthropicProvider.assistant_reply = _assistant_reply_impl
