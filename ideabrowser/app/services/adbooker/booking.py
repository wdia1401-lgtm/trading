"""Booking lifecycle: a strict state machine from reservation to completion.

awaiting_assets -> awaiting_approval -> awaiting_payment -> confirmed
                -> delivered -> completed   (cancelled from any pre-delivery state)

Every transition is validated against `Booking.TRANSITIONS`; illegal moves
raise `BookingError` and change nothing.
"""

from sqlalchemy.orm import Session

from ...ai import get_provider
from ...models import AdSlot, Booking, CreativeAsset
from .payments import get_gateway

REQUIRED_ASSET_KINDS = {"headline", "body_copy", "landing_url"}


class BookingError(Exception):
    pass


def _transition(db: Session, booking: Booking, new_status: str) -> Booking:
    if not booking.can_transition(new_status):
        raise BookingError(f"illegal transition {booking.status} -> {new_status}")
    booking.status = new_status
    db.flush()
    return booking


def create_booking(
    db: Session, slot: AdSlot, sponsor_id: int, brand_name: str, contact_email: str, notes: str = ""
) -> Booking:
    if slot.status != "available":
        raise BookingError(f"slot {slot.id} is {slot.status}, not available")
    booking = Booking(
        slot_id=slot.id,
        sponsor_id=sponsor_id,
        brand_name=brand_name,
        contact_email=contact_email,
        total_cents=slot.price_cents,
        notes=notes,
    )
    slot.status = "booked"
    db.add(booking)
    db.flush()
    return booking


def submit_asset(db: Session, booking: Booking, kind: str, content: str) -> CreativeAsset:
    if booking.status not in ("awaiting_assets", "awaiting_approval"):
        raise BookingError(f"cannot submit assets while booking is {booking.status}")
    if kind not in CreativeAsset.KINDS:
        raise BookingError(f"unknown asset kind '{kind}'")

    provider = get_provider()
    audience = f"{booking.slot.newsletter.niche} newsletter readers"
    review = provider.review_creative(kind, content, audience)

    asset = CreativeAsset(kind=kind, content=content, ai_review=review.model_dump())
    # Append via the relationship so the in-session collection stays current
    # (the auto-advance check below reads booking.assets).
    booking.assets.append(asset)
    db.flush()

    submitted_kinds = {a.kind for a in booking.assets}
    if booking.status == "awaiting_assets" and REQUIRED_ASSET_KINDS <= submitted_kinds:
        _transition(db, booking, "awaiting_approval")
    return asset


def review_asset(db: Session, asset: CreativeAsset, decision: str, feedback: str = "") -> CreativeAsset:
    """Operator approves/rejects a creative; booking advances when all approved."""
    if decision not in ("approved", "rejected"):
        raise BookingError("decision must be 'approved' or 'rejected'")
    asset.status = decision
    asset.feedback = feedback
    booking = asset.booking

    if decision == "rejected" and booking.status == "awaiting_approval":
        _transition(db, booking, "awaiting_assets")
    else:
        required_ok = all(
            any(a.kind == k and a.status == "approved" for a in booking.assets)
            for k in REQUIRED_ASSET_KINDS
        )
        no_pending = all(a.status != "pending" for a in booking.assets)
        if booking.status == "awaiting_approval" and required_ok and no_pending:
            _transition(db, booking, "awaiting_payment")
    db.flush()
    return asset


def pay(db: Session, booking: Booking):
    if booking.status != "awaiting_payment":
        raise BookingError(f"booking is {booking.status}; payment not due")
    gateway = get_gateway()
    payment = gateway.charge(db, booking)
    if payment.status == "succeeded":
        _transition(db, booking, "confirmed")
    return payment


def mark_delivered(db: Session, booking: Booking) -> Booking:
    booking = _transition(db, booking, "delivered")
    booking.slot.status = "delivered"
    db.flush()
    return booking


def complete(db: Session, booking: Booking) -> Booking:
    return _transition(db, booking, "completed")


def cancel(db: Session, booking: Booking) -> Booking:
    if booking.status in ("delivered", "completed", "cancelled"):
        raise BookingError(f"cannot cancel a {booking.status} booking")
    was_paid = booking.status == "confirmed"
    _transition(db, booking, "cancelled")
    booking.slot.status = "available"
    if was_paid:
        get_gateway().refund(db, booking)
    db.flush()
    return booking
