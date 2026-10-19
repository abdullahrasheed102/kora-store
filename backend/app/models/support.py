"""Return requests and support tickets."""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.extensions import db
from app.models.order import Order
from app.models.types import (
    CreatedAt,
    IntPK,
    ReturnCreatedBy,
    ReturnStatus,
    ReturnType,
    TicketPriority,
    TicketSource,
    TicketStatus,
    enum_column,
)
from app.models.user import normalize_email


class ReturnRequest(db.Model):
    __tablename__ = "return_requests"

    id: Mapped[IntPK]
    # No ON DELETE rule: Postgres refuses to delete an order that has return requests.
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    # [{"order_item_id": 12, "quantity": 1}, ...]. JSONB rather than a separate table:
    # a return is always read and written as a whole, and is rarely queried item by item.
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)
    type: Mapped[ReturnType] = mapped_column(enum_column(ReturnType, "return_type"))
    exchange_details: Mapped[str | None] = mapped_column(Text)  # e.g. "Size M instead of S"
    status: Mapped[ReturnStatus] = mapped_column(
        enum_column(ReturnStatus, "return_status"),
        default=ReturnStatus.REQUESTED,
        server_default=ReturnStatus.REQUESTED.value,
        index=True,
    )
    created_by: Mapped[ReturnCreatedBy] = mapped_column(
        enum_column(ReturnCreatedBy, "return_created_by")
    )
    created_at: Mapped[CreatedAt]

    order: Mapped[Order] = relationship(back_populates="return_requests")


class SupportTicket(db.Model):
    __tablename__ = "support_tickets"

    id: Mapped[IntPK]
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), index=True
    )
    email: Mapped[str] = mapped_column(String(254), index=True)
    name: Mapped[str] = mapped_column(String(120))
    subject: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)  # written by the agent, or the contact form message
    priority: Mapped[TicketPriority] = mapped_column(
        enum_column(TicketPriority, "ticket_priority"),
        default=TicketPriority.NORMAL,
        server_default=TicketPriority.NORMAL.value,
    )
    status: Mapped[TicketStatus] = mapped_column(
        enum_column(TicketStatus, "ticket_status"),
        default=TicketStatus.OPEN,
        server_default=TicketStatus.OPEN.value,
        index=True,
    )
    source: Mapped[TicketSource] = mapped_column(enum_column(TicketSource, "ticket_source"))
    created_at: Mapped[CreatedAt]

    order: Mapped[Order | None] = relationship()

    @validates("email")
    def _normalize_email(self, _key: str, value: str) -> str:
        return normalize_email(value)
