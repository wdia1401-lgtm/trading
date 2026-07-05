from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Idea(Base):
    """A startup idea with its full analytical payload.

    Structured sub-documents (audience, market, business model, GTM,
    execution) are JSON columns: they are written/read as whole units by the
    analysis pipeline and their shape is enforced at the Pydantic layer.
    """

    __tablename__ = "ideas"

    STATUSES = ("candidate", "curated", "archived")

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    tagline: Mapped[str] = mapped_column(String(300), default="")
    category: Mapped[str] = mapped_column(String(64), index=True, default="general")
    status: Mapped[str] = mapped_column(String(24), default="candidate", index=True)
    source: Mapped[str] = mapped_column(String(24), default="generated")  # generated | user_submitted

    problem_statement: Mapped[str] = mapped_column(Text, default="")
    solution_overview: Mapped[str] = mapped_column(Text, default="")
    why_now: Mapped[str] = mapped_column(Text, default="")

    # {segments: [...], demographics: str, psychographics: str, needs: [...]}
    target_audience: Mapped[dict] = mapped_column(JSON, default=dict)
    # {tam_usd, sam_usd, som_usd, cagr_pct, revenue_potential_usd_yr}
    market: Mapped[dict] = mapped_column(JSON, default=dict)
    # {model: str, revenue_streams: [{name, kind, pricing}], price_point_usd}
    business_model: Mapped[dict] = mapped_column(JSON, default=dict)
    # {channels: [...], first_100_customers: str, growth_loops: [...]}
    go_to_market: Mapped[dict] = mapped_column(JSON, default=dict)
    # {difficulty_1_10, technical, operational, capital_usd, time_to_mvp_weeks,
    #  required_skills: [...]}
    execution: Mapped[dict] = mapped_column(JSON, default=dict)
    # [{kind: "mockup"|"diagram"|"image", url, caption}]
    visual_assets: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    keywords: Mapped[list["IdeaKeyword"]] = relationship(
        back_populates="idea", cascade="all, delete-orphan"
    )
    signals: Mapped[list["Signal"]] = relationship(
        back_populates="idea", cascade="all, delete-orphan"
    )
    competitors: Mapped[list["Competitor"]] = relationship(
        back_populates="idea", cascade="all, delete-orphan"
    )
    validation_reports: Mapped[list["ValidationReport"]] = relationship(
        back_populates="idea", cascade="all, delete-orphan", order_by="ValidationReport.id.desc()"
    )
    framework_assessments: Mapped[list["FrameworkAssessment"]] = relationship(
        back_populates="idea", cascade="all, delete-orphan"
    )

    @property
    def latest_report(self) -> "ValidationReport | None":
        return self.validation_reports[0] if self.validation_reports else None


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(primary_key=True)
    term: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    monthly_volume: Mapped[int] = mapped_column(Integer, default=0)
    growth_pct_yoy: Mapped[float] = mapped_column(Float, default=0.0)
    competition: Mapped[str] = mapped_column(String(12), default="medium")  # low | medium | high
    cpc_usd: Mapped[float] = mapped_column(Float, default=0.0)


class IdeaKeyword(Base):
    __tablename__ = "idea_keywords"
    __table_args__ = (UniqueConstraint("idea_id", "keyword_id", name="uq_idea_keyword"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    idea_id: Mapped[int] = mapped_column(ForeignKey("ideas.id"), index=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id"))
    relevance: Mapped[float] = mapped_column(Float, default=1.0)

    idea: Mapped[Idea] = relationship(back_populates="keywords")
    keyword: Mapped[Keyword] = relationship()


class Signal(Base):
    """Proof/demand signal harvested from an external source."""

    __tablename__ = "signals"

    SOURCES = ("reddit", "x", "facebook", "google_trends", "news", "academic", "patents", "product_hunt", "other")

    id: Mapped[int] = mapped_column(primary_key=True)
    idea_id: Mapped[int] = mapped_column(ForeignKey("ideas.id"), index=True)
    source: Mapped[str] = mapped_column(String(24))
    kind: Mapped[str] = mapped_column(String(32), default="community_discussion")
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(500), default="")
    strength: Mapped[float] = mapped_column(Float, default=0.5)  # 0..1
    summary: Mapped[str] = mapped_column(Text, default="")
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    idea: Mapped[Idea] = relationship(back_populates="signals")


class Competitor(Base):
    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(primary_key=True)
    idea_id: Mapped[int] = mapped_column(ForeignKey("ideas.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    url: Mapped[str] = mapped_column(String(500), default="")
    kind: Mapped[str] = mapped_column(String(16), default="direct")  # direct | indirect
    positioning: Mapped[str] = mapped_column(Text, default="")
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, default=list)
    threat_level: Mapped[str] = mapped_column(String(12), default="medium")  # low | medium | high

    idea: Mapped[Idea] = relationship(back_populates="competitors")


class Trend(Base):
    __tablename__ = "trends"

    STAGES = ("emerging", "accelerating", "peaking", "declining")

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    category: Mapped[str] = mapped_column(String(64), default="general")
    momentum: Mapped[float] = mapped_column(Float, default=50.0)  # 0..100
    stage: Mapped[str] = mapped_column(String(16), default="emerging")
    summary: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class IdeaTrend(Base):
    __tablename__ = "idea_trends"
    __table_args__ = (UniqueConstraint("idea_id", "trend_id", name="uq_idea_trend"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    idea_id: Mapped[int] = mapped_column(ForeignKey("ideas.id"), index=True)
    trend_id: Mapped[int] = mapped_column(ForeignKey("trends.id"))

    trend: Mapped[Trend] = relationship()


class ValidationReport(Base):
    """Snapshot of the multi-dimensional validation of an idea."""

    __tablename__ = "validation_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    idea_id: Mapped[int] = mapped_column(ForeignKey("ideas.id"), index=True)
    overall_score: Mapped[float] = mapped_column(Float)  # 0..100
    # {problem_severity, market_potential, timing, competition_gap,
    #  feasibility, monetization, demand_evidence} each 0..100
    dimensions: Mapped[dict] = mapped_column(JSON, default=dict)
    verdict: Mapped[str] = mapped_column(String(32), default="promising")
    narrative: Mapped[str] = mapped_column(Text, default="")
    generated_by: Mapped[str] = mapped_column(String(32), default="deterministic")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    idea: Mapped[Idea] = relationship(back_populates="validation_reports")


class FrameworkAssessment(Base):
    """Result of applying one strategic framework to an idea."""

    __tablename__ = "framework_assessments"
    __table_args__ = (
        UniqueConstraint("idea_id", "framework", name="uq_idea_framework"),
    )

    FRAMEWORKS = ("value_equation", "acp", "market_matrix", "value_ladder")

    id: Mapped[int] = mapped_column(primary_key=True)
    idea_id: Mapped[int] = mapped_column(ForeignKey("ideas.id"), index=True)
    framework: Mapped[str] = mapped_column(String(32))
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    classification: Mapped[str] = mapped_column(String(64), default="")
    analysis: Mapped[str] = mapped_column(Text, default="")
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    idea: Mapped[Idea] = relationship(back_populates="framework_assessments")


class FounderFitAssessment(Base):
    __tablename__ = "founder_fit_assessments"
    __table_args__ = (UniqueConstraint("idea_id", "user_id", name="uq_fit_idea_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    idea_id: Mapped[int] = mapped_column(ForeignKey("ideas.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    score: Mapped[float] = mapped_column(Float)  # 0..100
    matched_skills: Mapped[list] = mapped_column(JSON, default=list)
    gaps: Mapped[list] = mapped_column(JSON, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DailyIdea(Base):
    """One deeply analyzed idea featured per day."""

    __tablename__ = "daily_ideas"

    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date, unique=True, index=True)
    idea_id: Mapped[int] = mapped_column(ForeignKey("ideas.id"))

    idea: Mapped[Idea] = relationship()
