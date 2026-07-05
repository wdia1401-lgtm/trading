"""Trend identification: derive momentum/stage from keyword telemetry."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Keyword, Trend


def stage_for(momentum: float) -> str:
    if momentum >= 80:
        return "peaking"
    if momentum >= 55:
        return "accelerating"
    if momentum >= 30:
        return "emerging"
    return "declining"


def momentum_from_keywords(keywords: list[Keyword]) -> float:
    """Blend search volume (reach) with YoY growth (velocity)."""
    if not keywords:
        return 40.0
    avg_growth = sum(k.growth_pct_yoy for k in keywords) / len(keywords)
    total_volume = sum(k.monthly_volume for k in keywords)
    volume_component = min(total_volume / 5_000, 40)  # caps at 200k combined volume
    growth_component = max(min(avg_growth, 150), -50) / 150 * 60
    return round(max(0.0, min(100.0, volume_component + growth_component)), 1)


def refresh_trend(db: Session, trend: Trend) -> Trend:
    """Recompute a trend's momentum/stage from its linked keyword terms."""
    if trend.keywords:
        kws = db.scalars(select(Keyword).where(Keyword.term.in_(trend.keywords))).all()
        if kws:
            trend.momentum = momentum_from_keywords(kws)
    trend.stage = stage_for(trend.momentum)
    db.flush()
    return trend


def list_trends(db: Session, category: str | None = None) -> list[Trend]:
    q = select(Trend).order_by(Trend.momentum.desc())
    if category:
        q = q.where(Trend.category == category)
    return list(db.scalars(q))
