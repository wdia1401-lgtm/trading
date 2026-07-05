"""Structured-output contracts for the AI provider layer.

These models double as the JSON schema handed to Claude's structured outputs
(`client.messages.parse`) and as the return type of the deterministic engine,
so both backends are interchangeable.
"""

from pydantic import BaseModel, Field


class RevenueStream(BaseModel):
    name: str
    kind: str = "subscription"  # subscription | one_time | usage | commission | ads
    pricing: str = ""


class IdeaDraft(BaseModel):
    """A fully-formed idea proposal produced from trend/signal context."""

    title: str
    tagline: str
    category: str = "general"
    problem_statement: str
    solution_overview: str
    why_now: str
    target_segments: list[str] = Field(default_factory=list)
    audience_needs: list[str] = Field(default_factory=list)
    tam_usd: int = 0
    sam_usd: int = 0
    som_usd: int = 0
    cagr_pct: float = 0.0
    business_model: str = "saas"
    revenue_streams: list[RevenueStream] = Field(default_factory=list)
    price_point_usd: float = 0.0
    gtm_channels: list[str] = Field(default_factory=list)
    first_100_customers: str = ""
    difficulty_1_10: int = 5
    time_to_mvp_weeks: int = 8
    required_skills: list[str] = Field(default_factory=list)
    capital_needed_usd: int = 0


class AnalysisNarrative(BaseModel):
    """Qualitative synthesis layered on top of the deterministic scores."""

    verdict: str = "promising"  # exceptional | strong | promising | risky | weak
    narrative: str
    top_strengths: list[str] = Field(default_factory=list)
    top_risks: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class CreativeReview(BaseModel):
    """AI feedback on a sponsor's ad creative."""

    score: int = Field(ge=0, le=100)
    suggestions: list[str] = Field(default_factory=list)
    improved_version: str = ""
