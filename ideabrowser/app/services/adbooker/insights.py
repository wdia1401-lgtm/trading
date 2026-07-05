"""Performance prediction and the operator analytics dashboard."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import AdSlot, Booking, Newsletter, PerformanceRecord
from ...schemas.adbooker import DashboardOut, PerformancePrediction
from .pricing import BASELINE_CTR


def predict_performance(db: Session, slot: AdSlot, creative_score: int | None = None) -> PerformancePrediction:
    """Forecast impressions/clicks for a slot from audience math + history.

    impressions = audience x open_rate; ctr = newsletter ctr x placement
    multiplier, nudged by the AI creative score when assets exist.
    """
    nl = slot.newsletter
    impressions = int(nl.audience_size * nl.open_rate)

    records = list(
        db.scalars(
            select(PerformanceRecord)
            .join(Booking, PerformanceRecord.booking_id == Booking.id)
            .join(AdSlot, Booking.slot_id == AdSlot.id)
            .where(AdSlot.newsletter_id == nl.id)
        )
    )
    if records:
        hist_impr = sum(r.impressions for r in records)
        hist_clicks = sum(r.clicks for r in records)
        base_ctr = hist_clicks / hist_impr if hist_impr else nl.click_rate
        confidence = "high" if len(records) >= 5 else "medium"
    else:
        base_ctr = nl.click_rate or BASELINE_CTR
        confidence = "low"

    ctr = base_ctr * slot.placement_type.ctr_multiplier
    creative_factor = 1.0
    if creative_score is not None:
        creative_factor = 0.8 + (creative_score / 100) * 0.4  # 0.8 .. 1.2
        ctr *= creative_factor

    clicks = int(impressions * ctr)
    return PerformancePrediction(
        booking_id=slot.booking.id if slot.booking else None,
        slot_id=slot.id,
        predicted_impressions=impressions,
        predicted_clicks=clicks,
        predicted_ctr=round(ctr, 5),
        confidence=confidence,
        drivers={
            "audience_size": nl.audience_size,
            "open_rate": nl.open_rate,
            "base_ctr": round(base_ctr, 5),
            "placement_multiplier": slot.placement_type.ctr_multiplier,
            "creative_factor": round(creative_factor, 3),
            "history_records": len(records),
        },
    )


def dashboard(db: Session, newsletter: Newsletter, window_days: int = 60) -> DashboardOut:
    start = date.today() - timedelta(days=window_days)
    end = date.today() + timedelta(days=window_days)
    slots = list(
        db.scalars(
            select(AdSlot).where(
                AdSlot.newsletter_id == newsletter.id,
                AdSlot.run_date >= start,
                AdSlot.run_date <= end,
            )
        )
    )
    bookings = [s.booking for s in slots if s.booking is not None]

    by_status: dict[str, int] = {}
    for b in bookings:
        by_status[b.status] = by_status.get(b.status, 0) + 1

    confirmed = sum(
        b.total_cents for b in bookings if b.status in ("confirmed", "delivered", "completed")
    )
    pending = sum(
        b.total_cents
        for b in bookings
        if b.status in ("awaiting_assets", "awaiting_approval", "awaiting_payment")
    )

    records = [
        r
        for b in bookings
        for r in db.scalars(select(PerformanceRecord).where(PerformanceRecord.booking_id == b.id))
    ]
    total_impr = sum(r.impressions for r in records)
    total_clicks = sum(r.clicks for r in records)
    avg_ctr = total_clicks / total_impr if total_impr else 0.0

    upcoming = sorted(
        (
            {
                "booking_id": b.id,
                "brand": b.brand_name,
                "run_date": b.slot.run_date.isoformat(),
                "placement": b.slot.placement_type.name,
                "status": b.status,
            }
            for b in bookings
            if b.status == "confirmed" and b.slot.run_date >= date.today()
        ),
        key=lambda r: r["run_date"],
    )[:10]

    booked = sum(1 for s in slots if s.status != "available")
    return DashboardOut(
        newsletter_id=newsletter.id,
        window_days=window_days,
        total_slots=len(slots),
        booked_slots=booked,
        occupancy_rate=round(booked / len(slots), 3) if slots else 0.0,
        revenue_confirmed_cents=confirmed,
        revenue_pending_cents=pending,
        bookings_by_status=by_status,
        avg_ctr=round(avg_ctr, 5),
        upcoming_deliveries=upcoming,
    )
