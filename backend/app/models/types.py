"""Enums and reusable column types shared by the models."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from sqlalchemy import Enum, func
from sqlalchemy.orm import mapped_column

# --- Reusable column types ---------------------------------------------------------------
# `Annotated` bundles a Python type with its column settings, so each model can just write
# `id: Mapped[IntPK]` instead of repeating the same mapped_column(...) everywhere.

IntPK = Annotated[int, mapped_column(primary_key=True)]
# Set by the database clock (server_default), so every row gets a time even from raw SQL.
CreatedAt = Annotated[datetime, mapped_column(server_default=func.now())]
UpdatedAt = Annotated[datetime, mapped_column(server_default=func.now(), onupdate=func.now())]


# --- Enums ---------------------------------------------------------------------------------
# StrEnum members are real strings: OrderStatus.SHIPPED == "shipped" is True, and they turn
# into JSON without any conversion.


class UserRole(StrEnum):
    CUSTOMER = "customer"
    ADMIN = "admin"


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    DELAYED = "delayed"
    PARTIALLY_SHIPPED = "partially_shipped"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class PaymentMethod(StrEnum):
    CARD = "card"  # hosted payment page (sandbox or Stripe); paid before we ship
    COD = "cod"  # cash on delivery: the courier collects cash when the parcel arrives


class PaymentStatus(StrEnum):
    UNPAID = "unpaid"
    PAID = "paid"
    REFUNDED = "refunded"  # the whole order amount was given back


class ShippingMethod(StrEnum):
    STANDARD = "standard"
    EXPRESS = "express"
    INTERNATIONAL = "international"


class EventActor(StrEnum):
    """Who caused an order event."""

    SYSTEM = "system"
    ADMIN = "admin"
    AGENT = "agent"


class ImageKind(StrEnum):
    PRODUCT = "product"  # the garment on its own, one per colour
    LIFESTYLE = "lifestyle"  # the garment being worn


class ReturnType(StrEnum):
    REFUND = "refund"
    EXCHANGE = "exchange"


class ReturnStatus(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    LABEL_SENT = "label_sent"
    RECEIVED = "received"
    REFUNDED = "refunded"
    REJECTED = "rejected"


class ReturnCreatedBy(StrEnum):
    CUSTOMER = "customer"
    AGENT = "agent"
    ADMIN = "admin"


class TicketPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class TicketSource(StrEnum):
    AGENT = "agent"
    CONTACT_FORM = "contact_form"


def enum_column(enum_cls: type[StrEnum], name: str) -> Enum:
    """Store an enum as VARCHAR + CHECK constraint, not as a native Postgres ENUM type.

    Adding a value to a native ENUM needs a special ALTER TYPE migration. A CHECK constraint
    is an ordinary migration, and the database still rejects unknown values.
    """
    return Enum(
        enum_cls,
        name=name,  # becomes the CHECK constraint name, e.g. ck_orders_order_status
        native_enum=False,
        create_constraint=True,
        length=32,  # room for longer values later without altering the column
        values_callable=lambda cls: [member.value for member in cls],  # store "shipped", not "SHIPPED"
        validate_strings=True,
    )
