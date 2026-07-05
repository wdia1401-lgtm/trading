from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class NewsletterCreate(BaseModel):
    operator_id: int
    name: str = Field(min_length=2, max_length=160)
    niche: str = "general"
    description: str = ""
    audience_size: int = Field(ge=0, default=0)
    open_rate: float = Field(ge=0, le=1, default=0.4)
    click_rate: float = Field(ge=0, le=1, default=0.02)
    send_days: list[int] = Field(default_factory=lambda: [0, 2, 4])


class NewsletterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    niche: str
    description: str
    audience_size: int
    open_rate: float
    click_rate: float
    send_days: list


class PlacementTypeCreate(BaseModel):
    name: str
    description: str = ""
    base_price_cents: int = Field(gt=0)
    max_per_issue: int = Field(ge=1, default=1)
    ctr_multiplier: float = Field(gt=0, default=1.0)


class PlacementTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    base_price_cents: int
    max_per_issue: int
    ctr_multiplier: float


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_date: date
    position: int
    price_cents: int
    status: str
    placement_type: PlacementTypeOut


class BookingCreate(BaseModel):
    sponsor_id: int
    brand_name: str = Field(min_length=1, max_length=160)
    contact_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    notes: str = ""


class AssetIn(BaseModel):
    kind: str
    content: str = Field(min_length=1)


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    content: str
    status: str
    feedback: str
    ai_review: dict


class AssetReviewIn(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    feedback: str = ""


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount_cents: int
    currency: str
    provider: str
    provider_ref: str
    invoice_number: str
    status: str


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slot_id: int
    sponsor_id: int
    brand_name: str
    contact_email: str
    total_cents: int
    status: str
    notes: str
    created_at: datetime
    assets: list[AssetOut] = []
    payments: list[PaymentOut] = []


class PricingSuggestion(BaseModel):
    slot_id: int
    run_date: date
    placement: str
    current_price_cents: int
    suggested_price_cents: int
    factors: dict  # {demand, lead_time, weekday, performance}
    rationale: str


class PerformancePrediction(BaseModel):
    booking_id: int | None = None
    slot_id: int
    predicted_impressions: int
    predicted_clicks: int
    predicted_ctr: float
    confidence: str  # low | medium | high
    drivers: dict


class DashboardOut(BaseModel):
    newsletter_id: int
    window_days: int
    total_slots: int
    booked_slots: int
    occupancy_rate: float
    revenue_confirmed_cents: int
    revenue_pending_cents: int
    bookings_by_status: dict
    avg_ctr: float
    upcoming_deliveries: list[dict]
