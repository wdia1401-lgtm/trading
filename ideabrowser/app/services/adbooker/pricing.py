"""Smart slot allocation: demand-, timing-, and performance-aware pricing.

suggested = base x demand x lead_time x weekday x performance, where each
factor is bounded so one signal can never swing the price more than ~35%.
Suggestions are advisory; `apply=true` writes them onto available slots.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import AdSlot, Booking, Newsletter, PerformanceRecord
from ...schemas.adbooker import PricingSuggestion
from .inventory import occupancy

BASELINE_CTR = 0.02


def _demand_factor(db: Session, slot: AdSlot) -> float:
    """Occupancy of the surrounding 4-week window; busy calendar -> price up."""
    window = occupancy(
        db, slot.newsletter_id, slot.run_date - timedelta(days=14), slot.run_date + timedelta(days=14)
    )
    return round(0.9 + window * 0.45, 3)  # 0.90 (empty) .. 1.35 (full)


def _lead_time_factor(slot: AdSlot, today: date | None = None) -> float:
    """Scarcity pricing near the send date; discount far-out inventory."""
    days_out = (slot.run_date - (today or date.today())).days
    if days_out <= 7:
        return 1.25
    if days_out <= 21:
        return 1.10
    if days_out <= 45:
        return 1.0
    return 0.92


def _weekday_factor(slot: AdSlot) -> float:
    """Tue-Thu sends historically outperform; price accordingly."""
    return {0: 1.0, 1: 1.08, 2: 1.08, 3: 1.05, 4: 0.97, 5: 0.9, 6: 0.9}[slot.run_date.weekday()]


def _performance_factor(db: Session, newsletter: Newsletter) -> float:
    """Newsletters whose delivered ads beat the baseline CTR earn a premium."""
    records = list(
        db.scalars(
            select(PerformanceRecord)
            .join(Booking, PerformanceRecord.booking_id == Booking.id)
            .join(AdSlot, Booking.slot_id == AdSlot.id)
            .where(AdSlot.newsletter_id == newsletter.id)
        )
    )
    if not records:
        return 1.0
    total_impr = sum(r.impressions for r in records)
    total_clicks = sum(r.clicks for r in records)
    realized_ctr = total_clicks / total_impr if total_impr else BASELINE_CTR
    ratio = realized_ctr / BASELINE_CTR
    return round(max(0.85, min(1.3, 0.7 + ratio * 0.3)), 3)


def suggest_prices(
    db: Session, newsletter: Newsletter, start: date | None = None, end: date | None = None,
    apply: bool = False,
) -> list[PricingSuggestion]:
    start = start or date.today()
    end = end or start + timedelta(days=60)
    perf = _performance_factor(db, newsletter)
    suggestions: list[PricingSuggestion] = []

    slots = db.scalars(
        select(AdSlot).where(
            AdSlot.newsletter_id == newsletter.id,
            AdSlot.run_date >= start,
            AdSlot.run_date <= end,
            AdSlot.status == "available",
        )
    )
    for slot in slots:
        factors = {
            "demand": _demand_factor(db, slot),
            "lead_time": _lead_time_factor(slot),
            "weekday": _weekday_factor(slot),
            "performance": perf,
        }
        multiplier = 1.0
        for f in factors.values():
            multiplier *= f
        suggested = int(round(slot.placement_type.base_price_cents * multiplier / 100) * 100)
        dominant = max(factors, key=lambda k: abs(factors[k] - 1))
        suggestions.append(
            PricingSuggestion(
                slot_id=slot.id,
                run_date=slot.run_date,
                placement=slot.placement_type.name,
                current_price_cents=slot.price_cents,
                suggested_price_cents=suggested,
                factors=factors,
                rationale=(
                    f"Base ${slot.placement_type.base_price_cents / 100:.0f} x {multiplier:.2f} "
                    f"(dominant factor: {dominant} at {factors[dominant]:.2f})"
                ),
            )
        )
        if apply:
            slot.price_cents = suggested
    if apply:
        db.flush()
    return suggestions
