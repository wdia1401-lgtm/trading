from datetime import date, timedelta

from app.services.adbooker import pricing
from tests.factories import make_newsletter, make_user


def test_suggestions_cover_available_slots_and_are_bounded(db):
    operator = make_user(db, "op2@x.com", role="operator")
    nl, pt = make_newsletter(db, operator)
    suggestions = pricing.suggest_prices(db, nl, date.today(), date.today() + timedelta(days=14))
    assert suggestions
    for s in suggestions:
        # every factor individually bounded; combined price stays within sane band
        for f in s.factors.values():
            assert 0.8 <= f <= 1.4
        assert 0.5 * pt.base_price_cents <= s.suggested_price_cents <= 2.5 * pt.base_price_cents
        assert s.rationale


def test_apply_writes_prices(db):
    operator = make_user(db, "op3@x.com", role="operator")
    nl, pt = make_newsletter(db, operator)
    suggestions = pricing.suggest_prices(db, nl, apply=True)
    by_id = {s.slot_id: s for s in suggestions}
    for slot in nl.slots:
        if slot.id in by_id:
            assert slot.price_cents == by_id[slot.id].suggested_price_cents


def test_near_dates_price_above_far_dates():
    class S:  # minimal stand-in with just a run_date
        pass

    s_near, s_far = S(), S()
    s_near.run_date = date.today() + timedelta(days=3)
    s_far.run_date = date.today() + timedelta(days=90)
    assert pricing._lead_time_factor(s_near) > pricing._lead_time_factor(s_far)
