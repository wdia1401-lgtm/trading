"""AdBooker: newsletter ad inventory, bookings, assets, payments, analytics."""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Newsletter(Base):
    __tablename__ = "newsletters"

    id: Mapped[int] = mapped_column(primary_key=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    niche: Mapped[str] = mapped_column(String(64), default="general")
    description: Mapped[str] = mapped_column(Text, default="")
    audience_size: Mapped[int] = mapped_column(Integer, default=0)
    open_rate: Mapped[float] = mapped_column(Float, default=0.4)   # 0..1
    click_rate: Mapped[float] = mapped_column(Float, default=0.02)  # 0..1 of opens
    send_days: Mapped[list] = mapped_column(JSON, default=lambda: [0, 2, 4])  # weekday ints (Mon=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    placement_types: Mapped[list["PlacementType"]] = relationship(
        back_populates="newsletter", cascade="all, delete-orphan"
    )
    slots: Mapped[list["AdSlot"]] = relationship(
        back_populates="newsletter", cascade="all, delete-orphan"
    )


class PlacementType(Base):
    """A sellable ad format within a newsletter (e.g. main sponsor, classified)."""

    __tablename__ = "placement_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    newsletter_id: Mapped[int] = mapped_column(ForeignKey("newsletters.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    base_price_cents: Mapped[int] = mapped_column(Integer)
    max_per_issue: Mapped[int] = mapped_column(Integer, default=1)
    # relative CTR of this placement vs the newsletter average (main sponsor > classified)
    ctr_multiplier: Mapped[float] = mapped_column(Float, default=1.0)

    newsletter: Mapped[Newsletter] = relationship(back_populates="placement_types")


class AdSlot(Base):
    """One bookable unit: a placement type on a specific send date."""

    __tablename__ = "ad_slots"
    __table_args__ = (
        UniqueConstraint(
            "newsletter_id", "placement_type_id", "run_date", "position",
            name="uq_slot_unit",
        ),
    )

    STATUSES = ("available", "held", "booked", "delivered")

    id: Mapped[int] = mapped_column(primary_key=True)
    newsletter_id: Mapped[int] = mapped_column(ForeignKey("newsletters.id"), index=True)
    placement_type_id: Mapped[int] = mapped_column(ForeignKey("placement_types.id"))
    run_date: Mapped[date] = mapped_column(Date, index=True)
    position: Mapped[int] = mapped_column(Integer, default=1)  # 1..max_per_issue
    price_cents: Mapped[int] = mapped_column(Integer)  # current (dynamic) price
    status: Mapped[str] = mapped_column(String(16), default="available", index=True)

    newsletter: Mapped[Newsletter] = relationship(back_populates="slots")
    placement_type: Mapped[PlacementType] = relationship()
    booking: Mapped["Booking | None"] = relationship(back_populates="slot", uselist=False)


class Booking(Base):
    """A sponsor's reservation of a slot, driven through a strict state machine.

    Lifecycle: awaiting_assets -> awaiting_approval -> awaiting_payment
               -> confirmed -> delivered -> completed
    `cancelled` is reachable from any pre-delivery state.
    """

    __tablename__ = "bookings"

    STATUSES = (
        "awaiting_assets",
        "awaiting_approval",
        "awaiting_payment",
        "confirmed",
        "delivered",
        "completed",
        "cancelled",
    )
    TRANSITIONS = {
        "awaiting_assets": {"awaiting_approval", "cancelled"},
        "awaiting_approval": {"awaiting_payment", "awaiting_assets", "cancelled"},
        "awaiting_payment": {"confirmed", "cancelled"},
        "confirmed": {"delivered", "cancelled"},
        "delivered": {"completed"},
        "completed": set(),
        "cancelled": set(),
    }

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("ad_slots.id"), unique=True)
    sponsor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    brand_name: Mapped[str] = mapped_column(String(160))
    contact_email: Mapped[str] = mapped_column(String(255))
    total_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="awaiting_assets", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    slot: Mapped[AdSlot] = relationship(back_populates="booking")
    assets: Mapped[list["CreativeAsset"]] = relationship(
        back_populates="booking", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="booking", cascade="all, delete-orphan"
    )

    def can_transition(self, new_status: str) -> bool:
        return new_status in self.TRANSITIONS.get(self.status, set())


class CreativeAsset(Base):
    __tablename__ = "creative_assets"

    KINDS = ("headline", "body_copy", "cta", "image", "logo", "landing_url")
    STATUSES = ("pending", "approved", "rejected")

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    content: Mapped[str] = mapped_column(Text)  # copy text, or URL/path for binary assets
    status: Mapped[str] = mapped_column(String(16), default="pending")
    feedback: Mapped[str] = mapped_column(Text, default="")
    ai_review: Mapped[dict] = mapped_column(JSON, default=dict)  # {score, suggestions: [...]}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    booking: Mapped[Booking] = relationship(back_populates="assets")


class Payment(Base):
    __tablename__ = "payments"

    STATUSES = ("requires_payment", "succeeded", "failed", "refunded")

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="usd")
    provider: Mapped[str] = mapped_column(String(24), default="mock")  # mock | stripe
    provider_ref: Mapped[str] = mapped_column(String(120), default="")
    invoice_number: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(24), default="requires_payment")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    booking: Mapped[Booking] = relationship(back_populates="payments")


class PerformanceRecord(Base):
    """Realized performance of a delivered ad — feeds pricing & prediction."""

    __tablename__ = "performance_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), unique=True)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    booking: Mapped[Booking] = relationship()

    @property
    def ctr(self) -> float:
        return self.clicks / self.impressions if self.impressions else 0.0
