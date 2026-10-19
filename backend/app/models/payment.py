"""Stripe webhook events we have already processed (for idempotency)."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.types import CreatedAt


class StripeEvent(db.Model):
    """One row per Stripe event id. Stripe may deliver the same event several times (retries,
    network hiccups). Inserting the id in the same transaction as the work means a duplicate
    hits the primary key and is skipped, and a failed attempt leaves no row, so the retry runs."""

    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # "evt_..."
    type: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[CreatedAt]

    def __repr__(self) -> str:
        return f"<StripeEvent {self.id} {self.type}>"

