from app.models import FrameworkAssessment
from app.services import frameworks
from tests.factories import enrich_idea, make_idea


def test_run_all_produces_four_assessments(db):
    idea = enrich_idea(db, make_idea(db))
    results = frameworks.run_all(db, idea)
    assert {r.framework for r in results} == set(FrameworkAssessment.FRAMEWORKS)
    for r in results:
        assert r.analysis
        assert r.recommendations


def test_run_all_is_idempotent_upsert(db):
    idea = enrich_idea(db, make_idea(db))
    frameworks.run_all(db, idea)
    frameworks.run_all(db, idea)
    db.flush()
    assert len(idea.framework_assessments) == 4


def test_market_matrix_quadrants(db):
    king = make_idea(
        db, title="King",
        market={"tam_usd": 40_000_000_000, "cagr_pct": 20},
        execution={"difficulty_1_10": 9, "time_to_mvp_weeks": 20},
        why_now="x" * 300,
    )
    low = make_idea(
        db, title="Low",
        market={"tam_usd": 1_000_000, "cagr_pct": 1},
        execution={"difficulty_1_10": 1, "time_to_mvp_weeks": 2},
        why_now="",
    )
    assert frameworks.market_matrix(king)["classification"] == "Category King"
    assert frameworks.market_matrix(low)["classification"] == "Low Impact"


def test_value_ladder_spans_free_to_continuity(db):
    idea = make_idea(db, title="Ladder")
    result = frameworks.value_ladder(idea)
    recs = result["recommendations"]
    assert len(recs) == 5
    assert recs[0].lower().startswith("bait")
    assert recs[-1].lower().startswith("continuity")


def test_value_equation_scores_bounded(db):
    idea = enrich_idea(db, make_idea(db))
    scores = frameworks.value_equation(idea)["scores"]
    for v in scores.values():
        assert 0 <= v <= 100
