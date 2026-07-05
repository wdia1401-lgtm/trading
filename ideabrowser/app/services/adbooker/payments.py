"""Payment gateway abstraction.

`MockGateway` ships with the repo (always succeeds, generates invoice
numbers). A production Stripe adapter implements the same two methods with
PaymentIntents + refunds and is selected via IDEABROWSER_PAYMENTS=stripe.
"""

import uuid
from typing import Protocol

from sqlalchemy.orm import Session

from ...config import settings
from ...models import Booking, Payment


class PaymentGateway(Protocol):
    name: str

    def charge(self, db: Session, booking: Booking) -> Payment: ...

    def refund(self, db: Session, booking: Booking) -> Payment | None: ...


def _invoice_number(booking: Booking) -> str:
    return f"INV-{booking.created_at:%Y%m}-{booking.id:05d}"


class MockGateway:
    name = "mock"

    def charge(self, db: Session, booking: Booking) -> Payment:
        payment = Payment(
            amount_cents=booking.total_cents,
            provider=self.name,
            provider_ref=f"mock_pi_{uuid.uuid4().hex[:16]}",
            invoice_number=_invoice_number(booking),
            status="succeeded",
        )
        booking.payments.append(payment)  # keep the in-session collection current
        db.flush()
        return payment

    def refund(self, db: Session, booking: Booking) -> Payment | None:
        succeeded = [p for p in booking.payments if p.status == "succeeded"]
        if not succeeded:
            return None
        refund = Payment(
            amount_cents=-succeeded[-1].amount_cents,
            provider=self.name,
            provider_ref=f"mock_re_{uuid.uuid4().hex[:16]}",
            invoice_number=succeeded[-1].invoice_number,
            status="refunded",
        )
        booking.payments.append(refund)
        db.flush()
        return refund


def get_gateway() -> PaymentGateway:
    # Extension point: `if settings.payment_provider == "stripe": return StripeGateway()`
    return MockGateway()
