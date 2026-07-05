"""Strategic framework engine.

Applies four business frameworks to an idea as deterministic scoring
functions (auditable, reproducible), producing scores, a classification,
analysis text, and recommendations for each. Persisted as
`FrameworkAssessment` rows (one per framework, upserted).
"""

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FrameworkAssessment, Idea


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _log_scale(value: float, ceiling: float) -> float:
    """Map value onto 0..100 with log compression against a ceiling."""
    if value <= 0:
        return 0.0
    return _clamp(100 * math.log10(1 + value) / math.log10(1 + ceiling))


# --------------------------------------------------------------------------
# 1. Value Equation (Hormozi): value = (dream outcome x likelihood)
#                                      / (time delay x effort & sacrifice)
# --------------------------------------------------------------------------
def value_equation(idea: Idea) -> dict:
    market = idea.market or {}
    execution = idea.execution or {}
    audience = idea.target_audience or {}

    dream = _clamp(
        _log_scale(market.get("revenue_potential_usd_yr", market.get("som_usd", 0)), 1e9) * 0.6
        + min(len(audience.get("needs", [])), 5) * 8
    )
    signal_strengths = [s.strength for s in idea.signals] or [0.3]
    likelihood = _clamp(sum(signal_strengths) / len(signal_strengths) * 70 + min(len(idea.signals), 6) * 5)
    mvp_weeks = execution.get("time_to_mvp_weeks", 12)
    time_delay = _clamp(mvp_weeks * 4, 5)          # higher = worse
    effort = _clamp(execution.get("difficulty_1_10", 5) * 10, 5)  # higher = worse

    raw = (max(dream, 1) * max(likelihood, 1)) / (time_delay * effort)
    score = _clamp(_log_scale(raw, 20) )

    weakest = min(
        [("dream outcome", dream), ("perceived likelihood", likelihood),
         ("time to value", 100 - time_delay), ("low effort", 100 - effort)],
        key=lambda kv: kv[1],
    )[0]
    return {
        "framework": "value_equation",
        "scores": {
            "dream_outcome": round(dream, 1),
            "perceived_likelihood": round(likelihood, 1),
            "time_delay_penalty": round(time_delay, 1),
            "effort_penalty": round(effort, 1),
            "value_score": round(score, 1),
        },
        "classification": "high-value offer" if score >= 60 else "needs offer engineering",
        "analysis": (
            f"The offer promises a dream outcome rated {dream:.0f}/100 with "
            f"{likelihood:.0f}/100 perceived likelihood, against a time-delay penalty of "
            f"{time_delay:.0f} and effort penalty of {effort:.0f}. Net value score: {score:.0f}/100. "
            f"The binding constraint is {weakest}."
        ),
        "recommendations": [
            f"Engineer the offer to improve its weakest lever: {weakest}.",
            "Add a fast time-to-first-value moment (result inside the first session).",
            "Stack proof (case studies, guarantees) to raise perceived likelihood.",
        ],
    }


# --------------------------------------------------------------------------
# 2. A.C.P. — Audience, Community, Product sequencing
# --------------------------------------------------------------------------
def acp(idea: Idea) -> dict:
    kws = [ik.keyword for ik in idea.keywords]
    total_volume = sum(k.monthly_volume for k in kws)
    audience_score = _clamp(_log_scale(total_volume, 500_000) * 0.7 + min(len(kws), 6) * 5)

    community_signals = [s for s in idea.signals if s.kind == "community_discussion"]
    community_score = _clamp(
        min(len(community_signals), 5) * 12
        + (sum(s.strength for s in community_signals) / len(community_signals) * 40 if community_signals else 10)
    )

    execution = idea.execution or {}
    bm = idea.business_model or {}
    product_score = _clamp(
        (10 - execution.get("difficulty_1_10", 5)) * 6
        + min(len(bm.get("revenue_streams", [])), 3) * 10
        + (10 if bm.get("model") else 0)
    )

    stages = {"audience": audience_score, "community": community_score, "product": product_score}
    focus = min(stages, key=stages.get)
    return {
        "framework": "acp",
        "scores": {k: round(v, 1) for k, v in stages.items()},
        "classification": f"start with {focus}",
        "analysis": (
            f"Audience {audience_score:.0f}, Community {community_score:.0f}, Product "
            f"{product_score:.0f}. The A.C.P. sequence says build the weakest layer first: "
            f"here that is {focus}. Ship product last — an owned audience and engaged "
            "community de-risk every later launch."
        ),
        "recommendations": [
            f"Prioritize {focus}-building for the next 30 days.",
            "Publish where the demand signals already are before building features.",
            "Convert community members into a design-partner cohort of 10-20 users.",
        ],
    }


# --------------------------------------------------------------------------
# 3. Market Matrix — Tech Novelty x Value quadrants
# --------------------------------------------------------------------------
def market_matrix(idea: Idea) -> dict:
    execution = idea.execution or {}
    market = idea.market or {}

    novelty_hint = len((idea.why_now or "")) / 12  # richer "why now" ~ tech/market shift
    novelty = _clamp(execution.get("difficulty_1_10", 5) * 7 + min(novelty_hint, 30))
    value = _clamp(_log_scale(market.get("tam_usd", 0), 5e10) * 0.7 + market.get("cagr_pct", 0) * 1.5)

    hi_n, hi_v = novelty >= 50, value >= 50
    quadrant = (
        "Category King" if hi_n and hi_v
        else "Commodity Play" if hi_v
        else "Tech Novelty" if hi_n
        else "Low Impact"
    )
    playbook = {
        "Category King": "Define the category vocabulary early and price for leadership.",
        "Commodity Play": "Win on distribution, brand, and unit economics — not invention.",
        "Tech Novelty": "Find the burning use case; novelty alone won't hold attention.",
        "Low Impact": "Reposition toward a higher-stakes problem or a bigger buyer.",
    }[quadrant]
    return {
        "framework": "market_matrix",
        "scores": {"tech_novelty": round(novelty, 1), "value_impact": round(value, 1)},
        "classification": quadrant,
        "analysis": (
            f"Tech novelty {novelty:.0f}/100 x value impact {value:.0f}/100 places this idea "
            f"in the '{quadrant}' quadrant. {playbook}"
        ),
        "recommendations": [playbook, "Re-plot the matrix after each major scope change."],
    }


# --------------------------------------------------------------------------
# 4. Value Ladder — Bait -> Frontend -> Core -> Backend/Continuity
# --------------------------------------------------------------------------
def value_ladder(idea: Idea) -> dict:
    bm = idea.business_model or {}
    core_price = float(bm.get("price_point_usd") or 49)
    rungs = [
        {"rung": "bait", "offer": "Free tool / report that solves one slice of the problem", "price_usd": 0},
        {"rung": "frontend", "offer": "Low-ticket starter (template pack, audit, trial)", "price_usd": round(max(core_price * 0.15, 5), 2)},
        {"rung": "core", "offer": bm.get("model", "core product subscription"), "price_usd": round(core_price, 2)},
        {"rung": "backend", "offer": "High-touch tier: onboarding, integrations, SLAs", "price_usd": round(core_price * 6, 2)},
        {"rung": "continuity", "offer": "Annual plan / retained services", "price_usd": round(core_price * 10, 2)},
    ]
    coverage = sum(1 for s in bm.get("revenue_streams", []) if s) / 5
    score = _clamp(40 + coverage * 40 + (20 if core_price > 0 else 0))
    return {
        "framework": "value_ladder",
        "scores": {"ladder_completeness": round(score, 1)},
        "classification": "monetization ladder drafted",
        "analysis": (
            f"Anchored on a core price of ${core_price:.0f}, the ladder spans a free bait "
            f"offer up to a ${core_price * 10:.0f} continuity tier. Current revenue-stream "
            f"coverage fills {coverage * 100:.0f}% of the ladder."
        ),
        "recommendations": [f"{r['rung'].title()}: {r['offer']} (${r['price_usd']})" for r in rungs],
    }


ALL_FRAMEWORKS = (value_equation, acp, market_matrix, value_ladder)


def run_all(db: Session, idea: Idea) -> list[FrameworkAssessment]:
    """Compute all four frameworks and upsert one assessment per framework."""
    existing = {
        fa.framework: fa
        for fa in db.scalars(
            select(FrameworkAssessment).where(FrameworkAssessment.idea_id == idea.id)
        )
    }
    results = []
    for fn in ALL_FRAMEWORKS:
        payload = fn(idea)
        fa = existing.get(payload["framework"])
        if fa is None:
            fa = FrameworkAssessment(idea_id=idea.id, framework=payload["framework"])
            db.add(fa)
        fa.scores = payload["scores"]
        fa.classification = payload["classification"]
        fa.analysis = payload["analysis"]
        fa.recommendations = payload["recommendations"]
        results.append(fa)
    db.flush()
    db.expire(idea, ["framework_assessments"])  # collection changed behind the relationship
    return results
