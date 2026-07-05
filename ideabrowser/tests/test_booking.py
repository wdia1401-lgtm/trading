import pytest

from app.models import AdSlot
from app.services.adbooker import booking as svc
from app.services.adbooker.booking import BookingError
from tests.factories import make_newsletter, make_user


def _available_slot(db, nl) -> AdSlot:
    return next(s for s in nl.slots if s.status == "available")


def _booked(db):
    operator = make_user(db, "op@x.com", role="operator")
    sponsor = make_user(db, "sp@x.com", role="sponsor")
    nl, _ = make_newsletter(db, operator)
    slot = _available_slot(db, nl)
    booking = svc.create_booking(db, slot, sponsor.id, "Brand", "sp@x.com")
    return nl, slot, booking


def test_booking_marks_slot_taken(db):
    nl, slot, booking = _booked(db)
    assert slot.status == "booked"
    assert booking.status == "awaiting_assets"
    with pytest.raises(BookingError):
        svc.create_booking(db, slot, booking.sponsor_id, "Other", "o@x.com")


def test_full_happy_path(db):
    nl, slot, booking = _booked(db)
    svc.submit_asset(db, booking, "headline", "Try our tool today")
    svc.submit_asset(db, booking, "body_copy", "It does the thing you need, with numbers: 3x faster.")
    svc.submit_asset(db, booking, "landing_url", "https://example.com")
    assert booking.status == "awaiting_approval"

    for asset in list(booking.assets):
        svc.review_asset(db, asset, "approved")
    assert booking.status == "awaiting_payment"

    payment = svc.pay(db, booking)
    assert payment.status == "succeeded"
    assert payment.invoice_number.startswith("INV-")
    assert booking.status == "confirmed"

    svc.mark_delivered(db, booking)
    assert slot.status == "delivered"
    svc.complete(db, booking)
    assert booking.status == "completed"


def test_ai_review_attached_on_submit(db):
    nl, slot, booking = _booked(db)
    asset = svc.submit_asset(db, booking, "cta", "amazing revolutionary synergy solution maybe")
    assert 0 <= asset.ai_review["score"] <= 100
    assert asset.ai_review["suggestions"]


def test_rejection_sends_back_to_assets(db):
    nl, slot, booking = _booked(db)
    svc.submit_asset(db, booking, "headline", "H")
    svc.submit_asset(db, booking, "body_copy", "B")
    svc.submit_asset(db, booking, "landing_url", "https://x.com")
    bad = booking.assets[0]
    svc.review_asset(db, bad, "rejected", feedback="too vague")
    assert booking.status == "awaiting_assets"
    assert bad.feedback == "too vague"


def test_illegal_transitions_rejected(db):
    nl, slot, booking = _booked(db)
    with pytest.raises(BookingError):
        svc.pay(db, booking)  # no approved assets yet
    with pytest.raises(BookingError):
        svc.mark_delivered(db, booking)
    with pytest.raises(BookingError):
        svc.complete(db, booking)


def test_cancel_after_payment_refunds_and_frees_slot(db):
    nl, slot, booking = _booked(db)
    svc.submit_asset(db, booking, "headline", "H")
    svc.submit_asset(db, booking, "body_copy", "B")
    svc.submit_asset(db, booking, "landing_url", "https://x.com")
    for asset in list(booking.assets):
        svc.review_asset(db, asset, "approved")
    svc.pay(db, booking)

    svc.cancel(db, booking)
    assert booking.status == "cancelled"
    assert slot.status == "available"
    assert any(p.status == "refunded" and p.amount_cents < 0 for p in booking.payments)
