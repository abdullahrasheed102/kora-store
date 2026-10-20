"""All models, importable from one place: `from app.models import Order, Product`.

Importing this package registers every table on `db.metadata`, which Alembic reads to
autogenerate migrations.
"""

from app.models.catalog import Product, ProductImage, ProductVariant
from app.models.email import EmailOutbox, VerifiedEmail
from app.models.newsletter import NewsletterSubscriber
from app.models.order import ORDER_NUMBER_START, Order, OrderEvent, OrderItem, order_number_seq
from app.models.payment import StripeEvent
from app.models.policy import Policy
from app.models.support import ReturnRequest, SupportTicket
from app.models.types import (
    EmailStatus,
    EventActor,
    ImageKind,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    ReturnCreatedBy,
    ReturnStatus,
    ReturnType,
    ShippingMethod,
    TicketPriority,
    TicketSource,
    TicketStatus,
    UserRole,
)
from app.models.user import Address, User, normalize_email

__all__ = [
    "ORDER_NUMBER_START",
    "Address",
    "EmailOutbox",
    "EmailStatus",
    "EventActor",
    "ImageKind",
    "NewsletterSubscriber",
    "Order",
    "OrderEvent",
    "OrderItem",
    "OrderStatus",
    "PaymentMethod",
    "PaymentStatus",
    "Policy",
    "Product",
    "ProductImage",
    "ProductVariant",
    "ReturnCreatedBy",
    "ReturnRequest",
    "ReturnStatus",
    "ReturnType",
    "ShippingMethod",
    "StripeEvent",
    "SupportTicket",
    "TicketPriority",
    "TicketSource",
    "TicketStatus",
    "User",
    "UserRole",
    "VerifiedEmail",
    "normalize_email",
    "order_number_seq",
]
