from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class _Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class KeywordOut(_Orm):
    term: str
    monthly_volume: int
    growth_pct_yoy: float
    competition: str
    cpc_usd: float


class SignalOut(_Orm):
    source: str
    kind: str
    title: str
    url: str
    strength: float
    summary: str


class CompetitorOut(_Orm):
    name: str
    url: str
    kind: str
    positioning: str
    strengths: list
    weaknesses: list
    threat_level: str


class TrendOut(_Orm):
    id: int
    name: str
    category: str
    momentum: float
    stage: str
    summary: str
    keywords: list


class ValidationReportOut(_Orm):
    overall_score: float
    dimensions: dict
    verdict: str
    narrative: str
    generated_by: str
    created_at: datetime


class FrameworkAssessmentOut(_Orm):
    framework: str
    scores: dict
    classification: str
    analysis: str
    recommendations: list


class FounderFitOut(_Orm):
    idea_id: int
    user_id: int
    score: float
    matched_skills: list
    gaps: list
    rationale: str


class IdeaSummary(_Orm):
    id: int
    slug: str
    title: str
    tagline: str
    category: str
    status: str
    source: str
    overall_score: float | None = None
    verdict: str | None = None


class IdeaDetail(IdeaSummary):
    problem_statement: str
    solution_overview: str
    why_now: str
    target_audience: dict
    market: dict
    business_model: dict
    go_to_market: dict
    execution: dict
    visual_assets: list
    created_at: datetime


class IdeaReport(BaseModel):
    """Full interactive report payload: idea + every analytical artifact."""

    idea: IdeaDetail
    validation: ValidationReportOut | None
    frameworks: list[FrameworkAssessmentOut]
    keywords: list[KeywordOut]
    signals: list[SignalOut]
    competitors: list[CompetitorOut]
    trends: list[TrendOut]


class IdeaCreate(BaseModel):
    """User-submitted idea; the platform runs the full analysis on intake."""

    title: str = Field(min_length=4, max_length=200)
    category: str = "general"
    problem_statement: str = Field(min_length=10)
    solution_overview: str = Field(min_length=10)
    target_audience: dict = Field(default_factory=dict)
    business_model: dict = Field(default_factory=dict)


class DailyIdeaOut(BaseModel):
    day: date
    report: IdeaReport
