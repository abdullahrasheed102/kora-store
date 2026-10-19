"""Support tickets. Created by the contact form now, and by the AI agent in phase 8."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, SupportTicket, TicketPriority, TicketSource, normalize_email
from app.returns import normalize_order_number


def create_ticket(
    session: Session,
    name: str,
    email: str,
    subject: str,
    summary: str,
    order_number: str | None,
    *,
    source: TicketSource = TicketSource.CONTACT_FORM,
    priority: TicketPriority = TicketPriority.NORMAL,
) -> SupportTicket:
    order = None
    number = normalize_order_number(order_number) if order_number else None
    if number:
        # Link the order only if the email matches it, so a ticket can't be attached to (and show
        # staff details of) someone else's order just by typing its number.
        order = session.scalars(
            select(Order).where(Order.order_number == number, Order.email == normalize_email(email))
        ).one_or_none()
    if order is None and number:
        summary = f"[Customer mentioned order {number}, which doesn't match their email]\n\n{summary}"
    ticket = SupportTicket(
        order=order, email=email, name=name.strip(), subject=subject.strip(), summary=summary.strip(),
        priority=priority, source=source,
    )
    session.add(ticket)
    session.commit()
    return ticket
