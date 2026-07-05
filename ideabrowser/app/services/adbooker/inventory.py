"""Ad inventory: slot generation and the Calendly-style availability calendar."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import AdSlot, Newsletter, PlacementType


def ensure_slots(db: Session, newsletter: Newsletter, start: date, end: date) -> int:
    """Materialize bookable slots for every send day x placement x position.

    Idempotent: existing slots are left untouched, so re-running for an
    overlapping window only fills gaps.
    """
    existing = {
        (s.placement_type_id, s.run_date, s.position)
        for s in db.scalars(
            select(AdSlot).where(
                AdSlot.newsletter_id == newsletter.id,
                AdSlot.run_date >= start,
                AdSlot.run_date <= end,
            )
        )
    }
    created = 0
    day = start
    while day <= end:
        if day.weekday() in (newsletter.send_days or []):
            for pt in newsletter.placement_types:
                for position in range(1, pt.max_per_issue + 1):
                    key = (pt.id, day, position)
                    if key not in existing:
                        db.add(
                            AdSlot(
                                newsletter_id=newsletter.id,
                                placement_type_id=pt.id,
                                run_date=day,
                                position=position,
                                price_cents=pt.base_price_cents,
                            )
                        )
                        created += 1
        day += timedelta(days=1)
    db.flush()
    return created


def calendar(
    db: Session,
    newsletter: Newsletter,
    start: date | None = None,
    end: date | None = None,
    only_available: bool = False,
) -> list[AdSlot]:
    start = start or date.today()
    end = end or start + timedelta(days=60)
    ensure_slots(db, newsletter, start, end)
    q = (
        select(AdSlot)
        .where(
            AdSlot.newsletter_id == newsletter.id,
            AdSlot.run_date >= start,
            AdSlot.run_date <= end,
        )
        .order_by(AdSlot.run_date, AdSlot.placement_type_id, AdSlot.position)
    )
    if only_available:
        q = q.where(AdSlot.status == "available")
    return list(db.scalars(q))


def occupancy(db: Session, newsletter_id: int, start: date, end: date) -> float:
    slots = list(
        db.scalars(
            select(AdSlot).where(
                AdSlot.newsletter_id == newsletter_id,
                AdSlot.run_date >= start,
                AdSlot.run_date <= end,
            )
        )
    )
    if not slots:
        return 0.0
    taken = sum(1 for s in slots if s.status != "available")
    return taken / len(slots)
