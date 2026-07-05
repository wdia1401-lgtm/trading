from typing import Protocol

from ..schemas.ai import AnalysisNarrative, CreativeReview, IdeaDraft


class AIProvider(Protocol):
    """Contract every AI backend implements."""

    name: str

    def draft_idea(self, context: str) -> IdeaDraft:
        """Turn trend/signal context into a fully-structured idea proposal."""
        ...

    def analyze_idea(self, idea_context: str, scores: dict[str, float]) -> AnalysisNarrative:
        """Write the qualitative synthesis over deterministic dimension scores."""
        ...

    def review_creative(self, kind: str, content: str, audience: str) -> CreativeReview:
        """Score an ad creative and suggest improvements."""
        ...

    def chat(self, system: str, history: list[dict[str, str]]) -> str:
        """Answer a conversational turn. `history` is [{role, content}, ...]."""
        ...
