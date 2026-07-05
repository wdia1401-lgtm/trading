"""Validation engine: multi-dimensional, data-grounded idea assessment.

Dimension scores are deterministic functions of the idea's structured data,
signals, keywords, and competitors — reproducible and explainable. The AI
provider then layers a qualitative narrative + verdict on top. Each run is
persisted as an immutable `ValidationReport` snapshot.
"""

import math

from sqlalchemy.orm import Session

from ..ai import get_provider
from ..models import Idea, ValidationReport

WEIGHTS = {
    "problem_severity": 0.18,
    "market_potential": 0.18,
    "timing": 0.15,
    "demand_evidence": 0.15,
    "competition_gap": 0.12,
    "feasibility": 0.12,
    "monetization": 0.10,
}


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def _log_scale(value: float, ceiling: float) -> float:
    if value <= 0:
        return 0.0
    return _clamp(100 * math.log10(1 + value) / math.log10(1 + ceiling))


def score_dimensions(idea: Idea) -> dict[str, float]:
    audience = idea.target_audience or {}
    market = idea.market or {}
    execution = idea.execution or {}
    bm = idea.business_model or {}

    problem = _clamp(
        min(len(idea.problem_statement or ""), 400) / 400 * 45
        + min(len(audience.get("needs", [])), 5) * 7
        + sum(10 for s in idea.signals if s.kind == "complaint")
    )

    market_potential = _clamp(
        _log_scale(market.get("tam_usd", 0), 5e10) * 0.55
        + _log_scale(market.get("som_usd", 0), 5e8) * 0.25
        + min(market.get("cagr_pct", 0), 25) * 0.8
    )

    kws = [ik.keyword for ik in idea.keywords]
    avg_growth = sum(k.growth_pct_yoy for k in kws) / len(kws) if kws else 0
    timing = _clamp(
        min(len(idea.why_now or ""), 300) / 300 * 40
        + min(avg_growth, 120) / 120 * 40
        + sum(4 for s in idea.signals if s.kind in ("search_growth", "funding", "launch"))
    )

    demand = _clamp(
        _log_scale(sum(k.monthly_volume for k in kws), 300_000) * 0.5
        + (sum(s.strength for s in idea.signals) / len(idea.signals) * 30 if idea.signals else 0)
        + min(len(idea.signals), 8) * 2.5
    )

    # Bell curve: zero competitors = unproven market, too many = crowded.
    n_comp = len(idea.competitors)
    high_threat = sum(1 for c in idea.competitors if c.threat_level == "high")
    competition = _clamp(75 - abs(n_comp - 3) * 9 - high_threat * 8 + 10)

    feasibility = _clamp(
        (10 - execution.get("difficulty_1_10", 5)) * 7
        + max(0, 26 - execution.get("time_to_mvp_weeks", 12))
        + (10 if execution.get("capital_usd", 100_000) <= 50_000 else 0)
    )

    monetization = _clamp(
        (25 if bm.get("model") else 0)
        + min(len(bm.get("revenue_streams", [])), 4) * 12
        + _log_scale(float(bm.get("price_point_usd") or 0), 1000) * 0.3
    )

    return {
        "problem_severity": round(problem, 1),
        "market_potential": round(market_potential, 1),
        "timing": round(timing, 1),
        "demand_evidence": round(demand, 1),
        "competition_gap": round(competition, 1),
        "feasibility": round(feasibility, 1),
        "monetization": round(monetization, 1),
    }


def overall_score(dimensions: dict[str, float]) -> float:
    return round(sum(dimensions[k] * w for k, w in WEIGHTS.items()), 1)


def idea_context(idea: Idea) -> str:
    """Compact textual context handed to the AI provider."""
    market = idea.market or {}
    lines = [
        f"{idea.title} — {idea.tagline}",
        f"- Category: {idea.category}",
        f"- Problem: {idea.problem_statement[:300]}",
        f"- Solution: {idea.solution_overview[:300]}",
        f"- Why now: {idea.why_now[:200]}",
        f"- TAM ${market.get('tam_usd', 0):,} / SOM ${market.get('som_usd', 0):,}",
        f"- Competitors: {', '.join(c.name for c in idea.competitors[:5]) or 'none catalogued'}",
        f"- Signals: {len(idea.signals)} across {len({s.source for s in idea.signals})} sources",
    ]
    return "\n".join(lines)


def validate_idea(db: Session, idea: Idea) -> ValidationReport:
    provider = get_provider()
    dims = score_dimensions(idea)
    total = overall_score(dims)
    narrative = provider.analyze_idea(idea_context(idea), dims)

    report = ValidationReport(
        idea_id=idea.id,
        overall_score=total,
        dimensions=dims,
        verdict=narrative.verdict,
        narrative=narrative.narrative,
        generated_by=provider.name,
    )
    db.add(report)
    db.flush()
    db.expire(idea, ["validation_reports"])  # keep idea.latest_report current
    return report
