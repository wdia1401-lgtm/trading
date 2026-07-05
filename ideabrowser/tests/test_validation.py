from app.services import validation
from tests.factories import enrich_idea, make_idea


def test_dimensions_bounded_and_complete(db):
    idea = enrich_idea(db, make_idea(db))
    dims = validation.score_dimensions(idea)
    assert set(dims) == set(validation.WEIGHTS)
    for v in dims.values():
        assert 0 <= v <= 100


def test_overall_score_is_weighted_average(db):
    dims = {k: 50.0 for k in validation.WEIGHTS}
    assert abs(validation.overall_score(dims) - 50.0) < 0.01


def test_richer_idea_scores_higher(db):
    bare = make_idea(db, title="Bare", market={}, business_model={}, why_now="",
                     problem_statement="short", execution={})
    rich = enrich_idea(db, make_idea(db, title="Rich"))
    bare_score = validation.overall_score(validation.score_dimensions(bare))
    rich_score = validation.overall_score(validation.score_dimensions(rich))
    assert rich_score > bare_score


def test_validate_idea_persists_snapshot(db):
    idea = enrich_idea(db, make_idea(db))
    report = validation.validate_idea(db, idea)
    assert report.id is not None
    assert report.generated_by == "deterministic"
    assert report.verdict in ("exceptional", "strong", "promising", "risky", "weak")
    assert report.narrative
    # snapshots accumulate (history preserved)
    validation.validate_idea(db, idea)
    assert len(idea.validation_reports) == 2
