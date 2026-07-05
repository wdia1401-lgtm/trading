"""Claude-backed provider using the official Anthropic SDK.

Structured artifacts (idea drafts, analyses, creative reviews) use
`client.messages.parse` with Pydantic output formats so responses are
schema-validated; chat uses a plain messages call.
"""

import anthropic

from ..schemas.ai import AnalysisNarrative, CreativeReview, IdeaDraft

_DRAFT_SYSTEM = (
    "You are a startup analyst who turns market signals into rigorous, "
    "specific startup idea proposals. Ground every field in the provided "
    "context; give realistic (not promotional) market numbers."
)
_ANALYSIS_SYSTEM = (
    "You are a venture analyst. You are given a startup idea and its "
    "deterministic dimension scores (0-100). Write a candid synthesis: "
    "verdict, narrative, top strengths, top risks, concrete next steps."
)
_CREATIVE_SYSTEM = (
    "You are a newsletter advertising expert. Review sponsor creatives for "
    "clarity, specificity, and call-to-action strength for the given audience."
)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str = "claude-opus-4-8") -> None:
        self.model = model
        self.client = anthropic.Anthropic()

    def _parse(self, system: str, prompt: str, output_format):
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=output_format,
        )
        return response.parsed_output

    def draft_idea(self, context: str) -> IdeaDraft:
        return self._parse(
            _DRAFT_SYSTEM,
            f"Market context:\n{context}\n\nPropose one startup idea as structured data.",
            IdeaDraft,
        )

    def analyze_idea(self, idea_context: str, scores: dict[str, float]) -> AnalysisNarrative:
        score_lines = "\n".join(f"- {k}: {v:.0f}/100" for k, v in scores.items())
        return self._parse(
            _ANALYSIS_SYSTEM,
            f"{idea_context}\n\nDimension scores:\n{score_lines}",
            AnalysisNarrative,
        )

    def review_creative(self, kind: str, content: str, audience: str) -> CreativeReview:
        return self._parse(
            _CREATIVE_SYSTEM,
            f"Asset kind: {kind}\nAudience: {audience}\nCreative:\n{content}",
            CreativeReview,
        )

    def chat(self, system: str, history: list[dict[str, str]]) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=system,
            messages=history,
        )
        return next((b.text for b in response.content if b.type == "text"), "")
