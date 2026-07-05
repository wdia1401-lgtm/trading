"""Seed the database with a realistic demo dataset.

Run:  python -m app.seed   (from the ideabrowser/ directory)

Creates users, trends, keywords, a hand-curated flagship idea with signals
and competitors, AI-generated ideas from trends, today's daily idea, and a
newsletter with live inventory plus one fully completed booking (so pricing
and prediction have history to learn from).
"""

from datetime import date, datetime, timedelta

from sqlalchemy import func, select

from .database import SessionLocal, init_db
from .models import (
    AdSlot,
    Competitor,
    DailyIdea,
    Idea,
    IdeaKeyword,
    Keyword,
    Newsletter,
    PerformanceRecord,
    PlacementType,
    Signal,
    Trend,
    User,
    UserProfile,
)
from .services import frameworks, generation, validation
from .services.adbooker import booking as booking_svc
from .services.adbooker import inventory


def _keyword(db, term, volume, growth, competition="medium", cpc=1.5) -> Keyword:
    kw = db.scalar(select(Keyword).where(Keyword.term == term))
    if kw is None:
        kw = Keyword(
            term=term, monthly_volume=volume, growth_pct_yoy=growth,
            competition=competition, cpc_usd=cpc,
        )
        db.add(kw)
        db.flush()
    return kw


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.scalar(select(User).limit(1)):
            print("Database already seeded — nothing to do.")
            return

        # ------------------------------------------------------------ users
        founder = User(email="mara@founder.dev", name="Mara Chen", role="founder")
        operator = User(email="ada@newsletter.io", name="Ada Okafor", role="operator")
        sponsor = User(email="sam@brandco.com", name="Sam Ruiz", role="sponsor")
        db.add_all([founder, operator, sponsor])
        db.flush()
        db.add(UserProfile(
            user_id=founder.id,
            skills=["python", "full-stack engineering", "product", "growth"],
            interests=["ai-tools", "fintech"],
            industries=["b2b-saas"],
            capital_available_usd=40_000,
            hours_per_week=30,
            risk_appetite="high",
            goals="Bootstrap a B2B SaaS to $30k MRR in 24 months.",
        ))

        # ----------------------------------------------------------- trends
        trend_specs = [
            ("AI compliance automation", "fintech", "Regulators are mandating model audits; "
             "mid-market firms lack tooling.", ["ai compliance software", "model audit tool"]),
            ("Vertical AI agents", "ai-tools", "Buyers now prefer domain-tuned agents over "
             "general chat interfaces.", ["ai agent for accounting", "legal ai assistant"]),
            ("Newsletter economy", "creator-economy", "Independent newsletters are becoming "
             "durable media businesses with real ad budgets.", ["newsletter sponsorship", "newsletter ads"]),
        ]
        keyword_specs = {
            "ai compliance software": (9_800, 96.0, "low", 8.2),
            "model audit tool": (2_400, 140.0, "low", 6.1),
            "ai agent for accounting": (5_600, 210.0, "medium", 4.4),
            "legal ai assistant": (12_000, 87.0, "high", 9.0),
            "newsletter sponsorship": (7_100, 44.0, "medium", 3.2),
            "newsletter ads": (4_300, 31.0, "medium", 2.9),
        }
        for term, (vol, growth, comp, cpc) in keyword_specs.items():
            _keyword(db, term, vol, growth, comp, cpc)

        trends = []
        for name, category, summary, kws in trend_specs:
            t = Trend(name=name, category=category, summary=summary, keywords=kws)
            db.add(t)
            trends.append(t)
        db.flush()
        from .services import trends as trend_svc
        for t in trends:
            trend_svc.refresh_trend(db, t)

        # ------------------------------------------- flagship curated idea
        flagship = Idea(
            slug="ai-compliance-copilot-for-community-banks",
            title="AI Compliance Copilot for Community Banks",
            tagline="Turn 40 hours of monthly compliance review into 4",
            category="fintech",
            status="curated",
            problem_statement=(
                "Community banks and credit unions face the same regulatory burden as "
                "national banks with 1% of the compliance headcount. Officers manually "
                "cross-reference every new lending policy against FFIEC, CFPB, and state "
                "rules; reviews take weeks, findings get missed, and consultants charge "
                "$300/hour to fill the gap."
            ),
            solution_overview=(
                "A compliance copilot that ingests the bank's policies and procedures, "
                "maps every clause to the applicable regulations, flags gaps and "
                "conflicts with citations, and drafts examiner-ready remediation memos. "
                "Ships as SOC2-ready SaaS with an on-prem option for core-averse IT teams."
            ),
            why_now=(
                "Regulator expectations for model risk management and fair-lending "
                "analytics jumped in the last two exam cycles, while LLM accuracy on "
                "regulatory-mapping tasks crossed the practical-usefulness threshold. "
                "Community banks are actively budgeting for compliance automation for "
                "the first time."
            ),
            target_audience={
                "segments": ["community banks ($100M-$5B assets)", "credit unions", "compliance consultancies"],
                "demographics": "US regulated depository institutions; buyer is the Chief Compliance Officer",
                "psychographics": "risk-averse, exam-cycle-driven, values auditability over novelty",
                "needs": ["pass exams without surprises", "cut consultant spend",
                          "keep pace with rule changes", "defensible audit trail"],
            },
            market={
                "tam_usd": 4_200_000_000, "sam_usd": 610_000_000, "som_usd": 38_000_000,
                "cagr_pct": 14.5, "revenue_potential_usd_yr": 38_000_000,
            },
            business_model={
                "model": "b2b saas",
                "revenue_streams": [
                    {"name": "Platform subscription", "kind": "subscription", "pricing": "$1,500-6,000/mo by asset size"},
                    {"name": "Exam-prep package", "kind": "one_time", "pricing": "$15k per exam cycle"},
                    {"name": "Policy-mapping API", "kind": "usage", "pricing": "metered"},
                ],
                "price_point_usd": 2_500,
            },
            go_to_market={
                "channels": ["state banking association partnerships", "compliance officer webinars",
                             "core-banking vendor marketplaces"],
                "first_100_customers": "Co-sell through two state banking associations; convert "
                                        "their annual-conference workshop attendees into design partners.",
                "growth_loops": ["examiner referrals", "consultant white-labeling"],
            },
            execution={
                "difficulty_1_10": 7, "time_to_mvp_weeks": 16, "capital_usd": 120_000,
                "required_skills": ["python", "ml engineering", "regulatory domain expertise",
                                     "enterprise sales"],
            },
            visual_assets=[{"kind": "diagram", "url": "/static/assets/compliance-flow.svg",
                            "caption": "Policy-to-regulation mapping pipeline"}],
        )
        db.add(flagship)
        db.flush()

        for term in ("ai compliance software", "model audit tool"):
            kw = _keyword(db, term, keyword_specs[term][0], keyword_specs[term][1])
            db.add(IdeaKeyword(idea_id=flagship.id, keyword_id=kw.id, relevance=0.95))

        signals = [
            ("reddit", "community_discussion", "r/banking thread: 'compliance is eating my week' (214 comments)", 0.8),
            ("reddit", "complaint", "Credit-union officer: 'we pay consultants $40k per exam cycle'", 0.85),
            ("google_trends", "search_growth", "'ai compliance software' interest up 96% YoY", 0.75),
            ("news", "funding", "Two RegTech seed rounds announced this quarter", 0.6),
            ("x", "community_discussion", "CCO thread on manual FFIEC mapping pain (1.2k likes)", 0.7),
        ]
        for source, kind, title, strength in signals:
            db.add(Signal(idea_id=flagship.id, source=source, kind=kind, title=title,
                          strength=strength, summary=title,
                          observed_at=datetime.utcnow() - timedelta(days=12)))

        competitors = [
            ("Ncontracts", "direct", "Enterprise GRC suite; heavy, expensive, weak AI", ["brand trust", "breadth"],
             ["slow implementation", "no policy-level AI mapping"], "medium"),
            ("Compliance.ai", "direct", "Reg-change feeds; alerts but no gap analysis", ["data coverage"],
             ["stops at notification", "no remediation drafting"], "medium"),
            ("Big-4 consultants", "indirect", "Manual review engagements", ["credibility"],
             ["$300+/hr", "not continuous"], "high"),
        ]
        for name, kind, positioning, strengths, weaknesses, threat in competitors:
            db.add(Competitor(idea_id=flagship.id, name=name, kind=kind, positioning=positioning,
                              strengths=strengths, weaknesses=weaknesses, threat_level=threat))
        db.flush()

        validation.validate_idea(db, flagship)
        frameworks.run_all(db, flagship)

        # ------------------------------------- AI-generated ideas per trend
        for t in trends:
            idea = generation.generate_from_trend(db, t)
            idea.status = "curated"

        # ------------------------------------------------------ daily idea
        db.add(DailyIdea(day=date.today(), idea_id=flagship.id))

        # -------------------------------------------------------- adbooker
        nl = Newsletter(
            operator_id=operator.id,
            name="The Bootstrapped Operator",
            slug="the-bootstrapped-operator",
            niche="b2b-saas",
            description="Weekly tactics for bootstrapped SaaS founders. 48k subscribers.",
            audience_size=48_000,
            open_rate=0.47,
            click_rate=0.024,
            send_days=[1, 3],  # Tue, Thu
        )
        db.add(nl)
        db.flush()
        main_spot = PlacementType(
            newsletter_id=nl.id, name="Main Sponsor",
            description="Top-of-email feature: logo, 80-word pitch, CTA button.",
            base_price_cents=95_000, max_per_issue=1, ctr_multiplier=1.6,
        )
        classified = PlacementType(
            newsletter_id=nl.id, name="Classified",
            description="One-line text ad in the classifieds block.",
            base_price_cents=15_000, max_per_issue=4, ctr_multiplier=0.6,
        )
        db.add_all([main_spot, classified])
        db.flush()

        # inventory: past 30 days (for the completed booking) + next 60 days
        inventory.ensure_slots(db, nl, date.today() - timedelta(days=30), date.today() + timedelta(days=60))

        # a completed historical booking with realized performance
        past_slot = db.scalar(
            select(AdSlot)
            .where(
                AdSlot.newsletter_id == nl.id,
                AdSlot.placement_type_id == main_spot.id,
                AdSlot.run_date < date.today(),
            )
            .order_by(AdSlot.run_date.desc())
        )
        done = booking_svc.create_booking(
            db, past_slot, sponsor.id, "LaunchDeck", "sam@brandco.com",
            notes="Q2 campaign for the analytics launch",
        )
        booking_svc.submit_asset(db, done, "headline", "Ship your launch page in 10 minutes")
        booking_svc.submit_asset(db, done, "body_copy",
                                 "LaunchDeck gives you 40+ conversion-tested sections, real A/B stats, "
                                 "and 1-click publish. Join 3,200 founders shipping faster.")
        booking_svc.submit_asset(db, done, "landing_url", "https://launchdeck.example.com/operator")
        for asset in list(done.assets):
            booking_svc.review_asset(db, asset, "approved")
        booking_svc.pay(db, done)
        booking_svc.mark_delivered(db, done)
        db.add(PerformanceRecord(booking_id=done.id, impressions=21_600, clicks=610, conversions=48))
        booking_svc.complete(db, done)

        # an upcoming confirmed booking
        future_slot = db.scalar(
            select(AdSlot)
            .where(
                AdSlot.newsletter_id == nl.id,
                AdSlot.placement_type_id == main_spot.id,
                AdSlot.run_date > date.today() + timedelta(days=7),
                AdSlot.status == "available",
            )
            .order_by(AdSlot.run_date)
        )
        upcoming = booking_svc.create_booking(
            db, future_slot, sponsor.id, "MetricsHQ", "sam@brandco.com",
        )
        booking_svc.submit_asset(db, upcoming, "headline", "Your SaaS metrics, finally in one place")
        booking_svc.submit_asset(db, upcoming, "body_copy",
                                 "MetricsHQ pulls Stripe, GA4, and your DB into one live board. "
                                 "Set up in 15 minutes — see churn risks 30 days earlier.")
        booking_svc.submit_asset(db, upcoming, "landing_url", "https://metricshq.example.com")
        for asset in list(upcoming.assets):
            booking_svc.review_asset(db, asset, "approved")
        booking_svc.pay(db, upcoming)

        db.commit()
        n_ideas = db.scalar(select(func.count(Idea.id)))
        print(
            f"Seeded: {n_ideas} ideas, 3 trends, newsletter '{nl.name}' with live "
            f"inventory, bookings #{done.id} (completed) and #{upcoming.id} (confirmed)."
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
