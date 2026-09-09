"""Provider registry.

One function, one import site. Swapping the AI backend is an environment
variable, not a refactor.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.ai.base import ResearchAIProvider
from app.services.ai.heuristic import HeuristicProvider


@lru_cache
def get_provider() -> ResearchAIProvider:
    name = get_settings().ai_provider.lower()
    if name == "anthropic":
        # Imported lazily so the default install needs no network stack.
        from app.services.ai.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    return HeuristicProvider()
