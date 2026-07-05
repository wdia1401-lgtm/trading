"""Idea generation & curation pipeline.

Flow: trend/signal context -> AI provider drafts a structured idea ->
persisted with slug de-duplication -> validation + frameworks run
immediately so every idea lands fully analyzed.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import get_provider
from ..models import Idea, IdeaTrend, Trend
from ..schemas.ai import IdeaDraft
from . import frameworks, validation


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:150] or "idea"


def _unique_slug(db: Session, base: str) -> str:
    slug, n = base, 2
    while db.scalar(select(Idea.id).where(Idea.slug == slug)) is not None:
        slug = f"{base}-{n}"
        n += 1
    return slug


def draft_to_idea(db: Session, draft: IdeaDraft, source: str = "generated") -> Idea:
    idea = Idea(
        slug=_unique_slug(db, slugify(draft.title)),
        title=draft.title,
        tagline=draft.tagline,
        category=draft.category,
        source=source,
        problem_statement=draft.problem_statement,
        solution_overview=draft.solution_overview,
        why_now=draft.why_now,
        target_audience={
            "segments": draft.target_segments,
            "needs": draft.audience_needs,
        },
        market={
            "tam_usd": draft.tam_usd,
            "sam_usd": draft.sam_usd,
            "som_usd": draft.som_usd,
            "cagr_pct": draft.cagr_pct,
            "revenue_potential_usd_yr": draft.som_usd,
        },
        business_model={
            "model": draft.business_model,
            "revenue_streams": [rs.model_dump() for rs in draft.revenue_streams],
            "price_point_usd": draft.price_point_usd,
        },
        go_to_market={
            "channels": draft.gtm_channels,
            "first_100_customers": draft.first_100_customers,
        },
        execution={
            "difficulty_1_10": draft.difficulty_1_10,
            "time_to_mvp_weeks": draft.time_to_mvp_weeks,
            "required_skills": draft.required_skills,
            "capital_usd": draft.capital_needed_usd,
        },
    )
    db.add(idea)
    db.flush()
    return idea


def generate_from_trend(db: Session, trend: Trend) -> Idea:
    """Generate one analyzed idea seeded by a market trend."""
    provider = get_provider()
    context = (
        f"{trend.name}\nCategory: {trend.category}. Momentum {trend.momentum:.0f}/100 "
        f"({trend.stage}). {trend.summary}\nRelated keywords: {', '.join(trend.keywords)}"
    )
    draft = provider.draft_idea(context)
    idea = draft_to_idea(db, draft)
    db.add(IdeaTrend(idea_id=idea.id, trend_id=trend.id))
    validation.validate_idea(db, idea)
    frameworks.run_all(db, idea)
    return idea


def analyze_new_idea(db: Session, idea: Idea) -> Idea:
    """Run the full analysis stack on a freshly created (e.g. user-submitted) idea."""
    validation.validate_idea(db, idea)
    frameworks.run_all(db, idea)
    return idea
