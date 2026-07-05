from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AdSlot, Booking, CreativeAsset, Newsletter, PerformanceRecord, PlacementType, User
from ..schemas.adbooker import (
    AssetIn,
    AssetOut,
    AssetReviewIn,
    BookingCreate,
    BookingOut,
    DashboardOut,
    NewsletterCreate,
    NewsletterOut,
    PaymentOut,
    PerformancePrediction,
    PlacementTypeCreate,
    PlacementTypeOut,
    PricingSuggestion,
    SlotOut,
)
from ..services.adbooker import booking as booking_service
from ..services.adbooker import insights, inventory, pricing
from ..services.adbooker.booking import BookingError
from ..services.generation import slugify
from .deps import get_or_404

router = APIRouter()


def _booking_guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except BookingError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# ---------------------------------------------------------- newsletters
@router.post("/newsletters", response_model=NewsletterOut, status_code=201)
def create_newsletter(payload: NewsletterCreate, db: Session = Depends(get_db)):
    get_or_404(db, User, payload.operator_id)
    data = payload.model_dump()
    slug = slugify(data["name"])
    if db.scalar(select(Newsletter).where(Newsletter.slug == slug)):
        raise HTTPException(status_code=409, detail="newsletter name already taken")
    nl = Newsletter(slug=slug, **data)
    db.add(nl)
    db.commit()
    return nl


@router.get("/newsletters", response_model=list[NewsletterOut])
def list_newsletters(db: Session = Depends(get_db)):
    return list(db.scalars(select(Newsletter)))


@router.get("/newsletters/{newsletter_id}", response_model=NewsletterOut)
def get_newsletter(newsletter_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Newsletter, newsletter_id)


@router.post(
    "/newsletters/{newsletter_id}/placements", response_model=PlacementTypeOut, status_code=201
)
def create_placement(newsletter_id: int, payload: PlacementTypeCreate, db: Session = Depends(get_db)):
    nl = get_or_404(db, Newsletter, newsletter_id)
    pt = PlacementType(newsletter_id=nl.id, **payload.model_dump())
    db.add(pt)
    db.commit()
    return pt


@router.get("/newsletters/{newsletter_id}/placements", response_model=list[PlacementTypeOut])
def list_placements(newsletter_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Newsletter, newsletter_id).placement_types


# ---------------------------------------------------------------- slots
@router.get("/newsletters/{newsletter_id}/slots", response_model=list[SlotOut])
def slot_calendar(
    newsletter_id: int,
    start: date | None = None,
    end: date | None = None,
    available_only: bool = False,
    db: Session = Depends(get_db),
):
    """Calendly-style availability calendar (slots are materialized on demand)."""
    nl = get_or_404(db, Newsletter, newsletter_id)
    slots = inventory.calendar(db, nl, start, end, only_available=available_only)
    db.commit()
    return slots


@router.get("/newsletters/{newsletter_id}/pricing-suggestions", response_model=list[PricingSuggestion])
def pricing_suggestions(
    newsletter_id: int,
    apply: bool = Query(default=False, description="write suggested prices onto available slots"),
    db: Session = Depends(get_db),
):
    """AI-optimized pricing across demand, lead time, weekday, and performance."""
    nl = get_or_404(db, Newsletter, newsletter_id)
    suggestions = pricing.suggest_prices(db, nl, apply=apply)
    db.commit()
    return suggestions


@router.get("/newsletters/{newsletter_id}/dashboard", response_model=DashboardOut)
def newsletter_dashboard(
    newsletter_id: int, window_days: int = Query(default=60, le=365), db: Session = Depends(get_db)
):
    nl = get_or_404(db, Newsletter, newsletter_id)
    return insights.dashboard(db, nl, window_days)


@router.get("/slots/{slot_id}/prediction", response_model=PerformancePrediction)
def slot_prediction(slot_id: int, db: Session = Depends(get_db)):
    """Forecast impressions/clicks for this slot before booking."""
    slot = get_or_404(db, AdSlot, slot_id)
    creative_score = None
    if slot.booking and slot.booking.assets:
        scores = [a.ai_review.get("score") for a in slot.booking.assets if a.ai_review]
        scores = [s for s in scores if s is not None]
        creative_score = int(sum(scores) / len(scores)) if scores else None
    return insights.predict_performance(db, slot, creative_score)


# ------------------------------------------------------------- bookings
@router.post("/slots/{slot_id}/book", response_model=BookingOut, status_code=201)
def book_slot(slot_id: int, payload: BookingCreate, db: Session = Depends(get_db)):
    slot = get_or_404(db, AdSlot, slot_id)
    get_or_404(db, User, payload.sponsor_id)
    booking = _booking_guard(
        booking_service.create_booking,
        db, slot, payload.sponsor_id, payload.brand_name, payload.contact_email, payload.notes,
    )
    db.commit()
    return booking


@router.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Booking, booking_id)


@router.post("/bookings/{booking_id}/assets", response_model=AssetOut, status_code=201)
def submit_asset(booking_id: int, payload: AssetIn, db: Session = Depends(get_db)):
    """Upload a creative asset; AI review runs automatically on intake."""
    booking = get_or_404(db, Booking, booking_id)
    asset = _booking_guard(booking_service.submit_asset, db, booking, payload.kind, payload.content)
    db.commit()
    return asset


@router.post("/assets/{asset_id}/review", response_model=AssetOut)
def review_asset(asset_id: int, payload: AssetReviewIn, db: Session = Depends(get_db)):
    """Operator approval/rejection; booking advances when required assets pass."""
    asset = get_or_404(db, CreativeAsset, asset_id)
    _booking_guard(booking_service.review_asset, db, asset, payload.decision, payload.feedback)
    db.commit()
    return asset


@router.post("/bookings/{booking_id}/pay", response_model=PaymentOut)
def pay_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = get_or_404(db, Booking, booking_id)
    payment = _booking_guard(booking_service.pay, db, booking)
    db.commit()
    return payment


class DeliveryIn(BaseModel):
    impressions: int = Field(ge=0, default=0)
    clicks: int = Field(ge=0, default=0)
    conversions: int = Field(ge=0, default=0)


@router.post("/bookings/{booking_id}/deliver", response_model=BookingOut)
def deliver_booking(booking_id: int, payload: DeliveryIn, db: Session = Depends(get_db)):
    """Mark the ad as sent and record realized performance (feeds pricing AI)."""
    booking = get_or_404(db, Booking, booking_id)
    _booking_guard(booking_service.mark_delivered, db, booking)
    db.add(PerformanceRecord(booking_id=booking.id, **payload.model_dump()))
    db.commit()
    return booking


@router.post("/bookings/{booking_id}/complete", response_model=BookingOut)
def complete_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = get_or_404(db, Booking, booking_id)
    _booking_guard(booking_service.complete, db, booking)
    db.commit()
    return booking


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = get_or_404(db, Booking, booking_id)
    _booking_guard(booking_service.cancel, db, booking)
    db.commit()
    return booking
