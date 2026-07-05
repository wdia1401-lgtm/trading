"""Personalization: founder-fit scoring and tailored idea recommendations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FounderFitAssessment, Idea, User, ValidationReport


def _norm(items: list[str]) -> set[str]:
    return {i.strip().lower() for i in items if i and i.strip()}


def founder_fit(db: Session, user: User, idea: Idea) -> FounderFitAssessment:
    """Score how well an idea matches a founder's skills, interests, and resources."""
    profile = user.profile
    skills = _norm(profile.skills if profile else [])
    interests = _norm((profile.interests if profile else []) + (profile.industries if profile else []))

    required = _norm((idea.execution or {}).get("required_skills", []))
    matched = sorted(skills & required)
    gaps = sorted(required - skills)
    skill_score = (len(matched) / len(required) * 100) if required else 50.0

    interest_score = 100.0 if idea.category.lower() in interests else (
        60.0 if any(i in (idea.title + idea.tagline).lower() for i in interests) else 25.0
    )

    capital_needed = (idea.execution or {}).get("capital_usd", 0)
    capital_have = profile.capital_available_usd if profile else 0
    resource_score = 100.0 if capital_have >= capital_needed else max(
        0.0, 100.0 * capital_have / capital_needed
    ) if capital_needed else 70.0

    difficulty = (idea.execution or {}).get("difficulty_1_10", 5)
    hours = profile.hours_per_week if profile else 10
    time_score = max(0.0, min(100.0, hours / max(difficulty, 1) * 18))

    score = round(skill_score * 0.4 + interest_score * 0.25 + resource_score * 0.2 + time_score * 0.15, 1)
    rationale = (
        f"Skill coverage {skill_score:.0f}% ({len(matched)}/{len(required) or 'n/a'} required skills), "
        f"interest alignment {interest_score:.0f}, capital readiness {resource_score:.0f}, "
        f"time-vs-difficulty {time_score:.0f}."
    )

    fit = db.scalar(
        select(FounderFitAssessment).where(
            FounderFitAssessment.idea_id == idea.id,
            FounderFitAssessment.user_id == user.id,
        )
    )
    if fit is None:
        fit = FounderFitAssessment(idea_id=idea.id, user_id=user.id, score=score)
        db.add(fit)
    fit.score = score
    fit.matched_skills = matched
    fit.gaps = gaps
    fit.rationale = rationale
    db.flush()
    return fit


def recommendations(db: Session, user: User, limit: int = 10) -> list[dict]:
    """Rank curated ideas by blended validation score + founder fit."""
    ideas = db.scalars(select(Idea).where(Idea.status.in_(("curated", "candidate")))).all()
    ranked = []
    for idea in ideas:
        report = db.scalar(
            select(ValidationReport)
            .where(ValidationReport.idea_id == idea.id)
            .order_by(ValidationReport.id.desc())
            .limit(1)
        )
        quality = report.overall_score if report else 50.0
        fit = founder_fit(db, user, idea)
        blended = round(quality * 0.55 + fit.score * 0.45, 1)
        ranked.append(
            {
                "idea_id": idea.id,
                "slug": idea.slug,
                "title": idea.title,
                "tagline": idea.tagline,
                "category": idea.category,
                "quality_score": quality,
                "fit_score": fit.score,
                "blended_score": blended,
                "why": fit.rationale,
            }
        )
    ranked.sort(key=lambda r: r["blended_score"], reverse=True)
    return ranked[:limit]
