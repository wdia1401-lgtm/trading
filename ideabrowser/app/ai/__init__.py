"""AI provider abstraction.

Every AI-powered feature goes through the `AIProvider` protocol, so backends
are swappable: `AnthropicProvider` (Claude, used when ANTHROPIC_API_KEY is
set) or `DeterministicProvider` (seeded heuristics, always available — keeps
the platform fully functional offline and makes tests reproducible).
"""

from functools import lru_cache

from ..config import settings
from .base import AIProvider
from .deterministic import DeterministicProvider


@lru_cache(maxsize=1)
def get_provider() -> AIProvider:
    if settings.ai_backend == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=settings.anthropic_model)
    return DeterministicProvider()


__all__ = ["AIProvider", "DeterministicProvider", "get_provider"]
