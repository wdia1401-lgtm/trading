"""Shared object builders for tests."""

from datetime import date, timedelta

from app.models import (
    Competitor,
    Idea,
    IdeaKeyword,
    Keyword,
    Newsletter,
    PlacementType,
    Signal,
    User,
)
from app.services.adbooker import inventory


def make_idea(db, title="Test Idea", **overrides) -> Idea:
    defaults = dict(
        slug=title.lower().replace(" ", "-"),
        title=title,
        tagline="A test idea",
        category="ai-tools",
        problem_statement="Practitioners waste twenty hours a week on manual work " * 3,
        solution_overview="Automate the workflow end to end with domain-tuned AI.",
        why_now="Model quality crossed the usefulness threshold recently and buyers have budget.",
        target_audience={"segments": ["ops teams"], "needs": ["save time", "accuracy", "adoption"]},
        market={"tam_usd": 2_000_000_000, "sam_usd": 300_000_000, "som_usd": 20_000_000, "cagr_pct": 12},
        business_model={
            "model": "saas",
            "revenue_streams": [{"name": "Pro", "kind": "subscription", "pricing": "$99/mo"}],
            "price_point_usd": 99,
        },
        go_to_market={"channels": ["SEO"], "first_100_customers": "communities"},
        execution={"difficulty_1_10": 5, "time_to_mvp_weeks": 8, "capital_usd": 30_000,
                   "required_skills": ["python", "product"]},
    )
    defaults.update(overrides)
    idea = Idea(**defaults)
    db.add(idea)
    db.flush()
    return idea


def enrich_idea(db, idea: Idea) -> Idea:
    kw = Keyword(term=f"kw-{idea.slug}", monthly_volume=40_000, growth_pct_yoy=80)
    db.add(kw)
    db.flush()
    db.add(IdeaKeyword(idea_id=idea.id, keyword_id=kw.id))
    db.add(Signal(idea_id=idea.id, source="reddit", kind="community_discussion",
                  title="big thread", strength=0.8))
    db.add(Signal(idea_id=idea.id, source="google_trends", kind="search_growth",
                  title="rising queries", strength=0.7))
    db.add(Competitor(idea_id=idea.id, name="Incumbent", positioning="legacy suite",
                      threat_level="medium"))
    db.flush()
    return idea


def make_user(db, email="t@example.com", role="founder") -> User:
    user = User(email=email, name="Test User", role=role)
    db.add(user)
    db.flush()
    return user


def make_newsletter(db, operator: User) -> tuple[Newsletter, PlacementType]:
    nl = Newsletter(
        operator_id=operator.id, name="Test Letter", slug="test-letter",
        niche="devtools", audience_size=10_000, open_rate=0.5, click_rate=0.02,
        send_days=[0, 1, 2, 3, 4],
    )
    db.add(nl)
    db.flush()
    pt = PlacementType(newsletter_id=nl.id, name="Main", base_price_cents=50_000,
                       max_per_issue=1, ctr_multiplier=1.5)
    db.add(pt)
    db.flush()
    inventory.ensure_slots(db, nl, date.today(), date.today() + timedelta(days=14))
    return nl, pt
