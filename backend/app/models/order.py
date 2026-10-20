"""Orders, the items in them, and the timeline of status changes."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Sequence, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.extensions import db
from app.models.types import (
    CreatedAt,
    EventActor,
    IntPK,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    ShippingMethod,
    UpdatedAt,
    enum_column,
)
from app.models.user import normalize_email

if TYPE_CHECKING:
    from app.models.catalog import ProductVariant
    from app.models.support import ReturnRequest
    from app.models.user import User

# A database counter for human-friendly order numbers. Postgres hands out each value exactly
# once, even under concurrent checkouts, so two orders can never get the same number.
ORDER_NUMBER_START = 1001
order_number_seq = Sequence("order_number_seq", start=ORDER_NUMBER_START, metadata=db.metadata)


class Order(db.Model):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint(
            "subtotal_cents >= 0 AND shipping_cents >= 0", name="amounts_not_negative"
        ),
        # The total can never disagree with its parts, whatever code wrote the row.
        CheckConstraint("total_cents = subtotal_cents + shipping_cents", name="total_adds_up"),
        # For the expiry job: "pending_payment orders older than X".
        Index("ix_orders_status_created_at", "status", "created_at"),
    )

    id: Mapped[IntPK]
    order_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        server_default=text("'KO-' || nextval('order_number_seq')"),
    )
    # NULL for guest checkout. SET NULL keeps the order if the account is ever deleted.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    email: Mapped[str] = mapped_column(String(254), index=True)  # tracking looks orders up by email
    customer_name: Mapped[str] = mapped_column(String(120))

    status: Mapped[OrderStatus] = mapped_column(
        enum_column(OrderStatus, "order_status"),
        default=OrderStatus.PENDING_PAYMENT,
        server_default=OrderStatus.PENDING_PAYMENT.value,
        index=True,
    )
    status_note: Mapped[str | None] = mapped_column(Text)

    subtotal_cents: Mapped[int]
    shipping_cents: Mapped[int]
    total_cents: Mapped[int]
    shipping_method: Mapped[ShippingMethod] = mapped_column(
        enum_column(ShippingMethod, "shipping_method")
    )

    # How the customer pays, and whether the money has arrived. Separate from `status` (where the
    # parcel is): a cash-on-delivery order is "processing" but still "unpaid" until the courier
    # collects the cash.
    payment_method: Mapped[PaymentMethod] = mapped_column(
        enum_column(PaymentMethod, "payment_method"),
        default=PaymentMethod.CARD,
        server_default=PaymentMethod.CARD.value,
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        enum_column(PaymentStatus, "payment_status"),
        default=PaymentStatus.UNPAID,
        server_default=PaymentStatus.UNPAID.value,
    )
    # Required for cash on delivery, so the courier can call before arriving. Shown to admins only.
    phone: Mapped[str | None] = mapped_column(String(30))

    # The address is copied onto the order (not linked to `addresses`), so editing a saved
    # address later never changes where a past order was sent.
    shipping_line1: Mapped[str] = mapped_column(String(200))
    shipping_line2: Mapped[str | None] = mapped_column(String(200))
    shipping_city: Mapped[str] = mapped_column(String(100))
    shipping_state: Mapped[str | None] = mapped_column(String(100))
    shipping_postal_code: Mapped[str] = mapped_column(String(20))
    shipping_country: Mapped[str] = mapped_column(String(2))

    carrier: Mapped[str | None] = mapped_column(String(40))
    tracking_number: Mapped[str | None] = mapped_column(String(64))
    estimated_delivery: Mapped[date | None]
    delivered_at: Mapped[datetime | None]

    # Unique, so a Stripe webhook delivered twice can't create or pay for two orders (phase 4).
    # Holds the secret that proves you're the buyer on the thank-you page: the payment provider's
    # session id for card orders, or a random "cod_..." token for cash-on-delivery orders.
    stripe_session_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    stripe_payment_intent: Mapped[str | None] = mapped_column(String(255), unique=True)

    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    user: Mapped[User | None] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id"
    )
    events: Mapped[list[OrderEvent]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="(OrderEvent.created_at, OrderEvent.id)",
    )
    return_requests: Mapped[list[ReturnRequest]] = relationship(back_populates="order")

    @validates("email")
    def _normalize_email(self, _key: str, value: str) -> str:
        return normalize_email(value)

    def __repr__(self) -> str:
        return f"<Order {self.order_number} {self.status}>"


class OrderItem(db.Model):
    """One line of an order.

    Name, size, color, price and final-sale flag are *snapshots* copied at purchase time.
    If the product is renamed or repriced later, the order still shows what was paid.
    """

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price_cents >= 0", name="price_not_negative"),
    )

    id: Mapped[IntPK]
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    # Kept for stock updates and links; SET NULL because the snapshot below is enough on its own.
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="SET NULL"), index=True
    )
    product_name: Mapped[str] = mapped_column(String(160))
    size: Mapped[str] = mapped_column(String(20))
    color: Mapped[str] = mapped_column(String(40))
    unit_price_cents: Mapped[int]
    quantity: Mapped[int]
    is_final_sale: Mapped[bool] = mapped_column(default=False, server_default="false")

    order: Mapped[Order] = relationship(back_populates="items")
    variant: Mapped[ProductVariant | None] = relationship()

    @property
    def line_total_cents(self) -> int:
        return self.unit_price_cents * self.quantity


class OrderEvent(db.Model):
    """One step in an order's history. Rows are only ever added, never edited (an audit trail)."""

    __tablename__ = "order_events"
    __table_args__ = (Index("ix_order_events_order_id_created_at", "order_id", "created_at"),)

    id: Mapped[IntPK]
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    status: Mapped[OrderStatus] = mapped_column(enum_column(OrderStatus, "order_status"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[CreatedAt]
    created_by: Mapped[EventActor] = mapped_column(
        enum_column(EventActor, "event_actor"),
        default=EventActor.SYSTEM,
        server_default=EventActor.SYSTEM.value,
    )

    order: Mapped[Order] = relationship(back_populates="events")

    def __repr__(self) -> str:
        return f"<OrderEvent {self.status} at {self.created_at:%Y-%m-%d %H:%M}>"
