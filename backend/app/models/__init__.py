"""All models, importable from one place: `from app.models import Order, Product`.

Importing this package registers every table on `db.metadata`, which Alembic reads to
autogenerate migrations.
"""

from app.models.catalog import Product, ProductVariant
from app.models.order import ORDER_NUMBER_START, Order, OrderEvent, OrderItem, order_number_seq
from app.models.policy import Policy
from app.models.support import ReturnRequest, SupportTicket
from app.models.types import (
    EventActor,
    OrderStatus,
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
    "EventActor",
    "Order",
    "OrderEvent",
    "OrderItem",
    "OrderStatus",
    "Policy",
    "Product",
    "ProductVariant",
    "ReturnCreatedBy",
    "ReturnRequest",
    "ReturnStatus",
    "ReturnType",
    "ShippingMethod",
    "SupportTicket",
    "TicketPriority",
    "TicketSource",
    "TicketStatus",
    "User",
    "UserRole",
    "normalize_email",
    "order_number_seq",
]
