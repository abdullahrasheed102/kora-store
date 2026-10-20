"""Automatic emails (docs/AI_PLAN.md section 4). Plain code that reacts to changes, not AI.

Each function here only ENQUEUES an email: it adds an outbox row to the caller's open transaction
and never commits. So the email exists only if the caller's change is committed (see
app/mail/outbox.py). Call them just before the commit that makes the change real.

Today the checkout, the admin pages and the contact form call these. In phase 8D the admin
Copilot calls the same functions after the admin approves an action, so every path sends the
same emails.
"""

import logging
import secrets
from datetime import date
from typing import Any

from flask import current_app
from sqlalchemy.orm import Session

from app.mail.outbox import enqueue, is_blocked
from app.mail.verification import is_verified, make_token, verify_url
from app.models import Order, OrderEvent, OrderStatus, PaymentMethod, ReturnRequest, ReturnType, ShippingMethod, SupportTicket, User
from app.returns import refund_estimate_cents, return_shipping

log = logging.getLogger(__name__)

SHIPPING_LABELS = {
    ShippingMethod.STANDARD: "Standard shipping",
    ShippingMethod.EXPRESS: "Express shipping",
    ShippingMethod.INTERNATIONAL: "International shipping",
}
DISPATCH_STATUSES = {OrderStatus.SHIPPED, OrderStatus.PARTIALLY_SHIPPED}
# status -> (headline, subject, message). "{n}" is the order number.
STATUS_UPDATES = {
    OrderStatus.OUT_FOR_DELIVERY: (
        "Out for delivery today",
        "Your order {n} is out for delivery",
        "your order is with the courier and should arrive today.",
    ),
    OrderStatus.DELIVERED: (
        "Your order has arrived",
        "Your order {n} was delivered",
        "your order has been delivered. We hope you love it.",
    ),
    OrderStatus.DELAYED: (
        "Your order is delayed",
        "Your order {n} is delayed",
        "your order is taking longer than we expected. We're sorry for the wait.",
    ),
}


# --- orders -------------------------------------------------------------------------------------


def order_placed(session: Session, order: Order) -> None:
    """A card order was paid, or a cash-on-delivery order was placed.

    A verified address gets the confirmation now. An unverified one (a guest, or an account that
    hasn't clicked its link yet) first gets one short "is this your email?" message. Clicking it
    sends the confirmation (app/mail/verification.py).
    """
    if is_blocked(order.email) or is_verified(session, order.email):
        order_confirmation(session, order)  # a blocked address is recorded as suppressed
        return
    enqueue(
        session,
        key=f"confirm-order-email:{order.id}",
        kind="confirm_order_email",
        to=order.email,
        context={"order_number": order.order_number, "verify_url": verify_url(make_token(order.email, order.id))},
        reply_to=_reply_to(),
        order_id=order.id,
    )


def order_confirmation(session: Session, order: Order) -> None:
    _to_customer(session, order, key=f"order-confirmation:{order.id}", kind="order_confirmation")


def order_status_changed(session: Session, order: Order, event: OrderEvent) -> None:
    """Shipped, out for delivery, delivered or delayed. Other statuses send nothing here.

    Keyed by the event id: an order can be delayed twice, and each delay is news worth an email.
    """
    key = f"order-status:{order.id}:{event.id}"
    if event.status in DISPATCH_STATUSES:
        _to_customer(session, order, key=key, kind="order_dispatched", **dispatch_context(order, event.status))
    elif event.status in STATUS_UPDATES:
        _to_customer(session, order, key=key, kind="order_update", **update_context(order, event.status))


def order_cancelled(session: Session, order: Order, *, refund_cents: int, note: str | None = None) -> None:
    """The store cancelled a confirmed order. Called after an admin approves the cancellation.

    `refund_cents` is what goes back to the card (0 for cash on delivery: nothing was paid).
    """
    _to_customer(
        session, order, key=f"order-cancelled:{order.id}", kind="order_cancelled",
        **cancel_context(order, refund_cents), note=note,
    )


# --- returns ------------------------------------------------------------------------------------
# A return moves through each status at most once (the state machine in app/admin.py), so the
# return id + status is a natural idempotency key.


def return_approved(session: Session, request: ReturnRequest, note: str | None = None) -> None:
    _to_customer(
        session, request.order, key=f"return:{request.id}:approved", kind="return_approved",
        ret=return_context(request), note=note,
    )


def return_rejected(session: Session, request: ReturnRequest, note: str) -> None:
    _to_customer(
        session, request.order, key=f"return:{request.id}:rejected", kind="return_rejected",
        ret=return_context(request), note=note,
    )


def refund_issued(session: Session, request: ReturnRequest, amount_cents: int, note: str | None = None) -> None:
    _to_customer(
        session, request.order, key=f"return:{request.id}:refunded", kind="refund_issued",
        ret=return_context(request), refund=refund_context(request.order, amount_cents), note=note,
    )


# --- template data -----------------------------------------------------------------------------------
# Pure functions (no database, no sending), shared with `flask email preview`, so a preview
# always shows exactly what a real email would.


def dispatch_context(order: Order, status: OrderStatus) -> dict[str, Any]:
    return {
        "partial": status is OrderStatus.PARTIALLY_SHIPPED,
        "shipment": {
            "carrier": order.carrier,
            "tracking_number": order.tracking_number,
            "estimated_delivery": _long_date(order.estimated_delivery),
            "note": order.status_note,
        },
    }


def update_context(order: Order, status: OrderStatus) -> dict[str, Any]:
    headline, subject, message = STATUS_UPDATES[status]
    in_transit = status is not OrderStatus.DELIVERED
    return {
        "update": {
            "status": status.value,
            "headline": headline,
            "subject": subject.format(n=order.order_number),
            "message": message,
            "note": order.status_note,
            "carrier": order.carrier if in_transit else None,
            "tracking_number": order.tracking_number if in_transit else None,
            "estimated_delivery": _long_date(order.estimated_delivery) if status is OrderStatus.DELAYED else None,
        }
    }


def cancel_context(order: Order, refund_cents: int) -> dict[str, Any]:
    if refund_cents:
        refund = {
            "summary": f"We've refunded {money(refund_cents)} to your original payment method.",
            "detail": "Refunds usually show on your statement within 5–7 business days.",
        }
    elif order.payment_method is PaymentMethod.COD:
        refund = {"summary": "You chose cash on delivery and haven't paid anything, so there's nothing to refund.", "detail": None}
    else:
        refund = {"summary": "You weren't charged for this order.", "detail": None}
    return {"refund": refund}


def refund_context(order: Order, amount_cents: int) -> dict[str, Any]:
    if order.payment_method is PaymentMethod.COD:
        # No card to refund: staff pay it by bank transfer or store credit (refunds policy).
        return {"amount": money(amount_cents), "how": "By bank transfer or store credit",
                "detail": "We'll contact you to arrange it, whichever you prefer."}
    return {"amount": money(amount_cents), "how": "To your original payment method",
            "detail": "It usually shows on your statement within 5–7 business days."}


def return_context(request: ReturnRequest) -> dict[str, Any]:
    order = request.order
    items = {item.id: item for item in order.items}
    lines = []
    for line in request.items:
        item = items[line["order_item_id"]]
        lines.append(f"{line['quantity']} × {item.product_name} ({item.color} / {item.size})")
    if request.type is ReturnType.EXCHANGE:
        after = "Once it arrives, we'll send out your new size or colour."
    else:
        how = "by bank transfer or store credit" if order.payment_method is PaymentMethod.COD else "to your original payment method"
        after = f"Once it arrives at our warehouse, we'll refund {money(refund_estimate_cents(request))} {how}."
    return {
        # A refund-type request is still "your return" to the customer.
        "kind": "exchange" if request.type is ReturnType.EXCHANGE else "return",
        "lines": lines,
        "exchange_details": request.exchange_details,
        "prepaid_label": return_shipping(order) == "prepaid_label",
        "after_receipt": after,
    }


# --- staff and accounts -----------------------------------------------------------------------------


def ticket_created(session: Session, ticket: SupportTicket) -> None:
    """Alert the store owner. Goes to ADMIN_NOTIFY_EMAIL, our own address, so it needs no verification."""
    admin_email = current_app.config["ADMIN_NOTIFY_EMAIL"]
    if not admin_email:
        log.info("Ticket %s created; ADMIN_NOTIFY_EMAIL is not set, so no alert email", ticket.id)
        return
    enqueue(
        session, key=f"ticket-alert:{ticket.id}", kind="ticket_alert", to=admin_email, context=ticket_context(ticket),
        reply_to=ticket.email,  # "Reply" in the owner's inbox answers the customer directly
    )


def ticket_context(ticket: SupportTicket) -> dict[str, Any]:
    site = current_app.config["FRONTEND_URL"].rstrip("/")
    return {
        "audience": "admin",
        "ticket": {
            "id": ticket.id,
            "subject": ticket.subject,
            "name": ticket.name,
            "email": ticket.email,
            "priority": ticket.priority.value,
            "source": ticket.source.value.replace("_", " "),
            "summary": ticket.summary,
            "order_number": ticket.order.order_number if ticket.order else None,
            "admin_url": f"{site}/admin/tickets",
        },
    }


def account_verification(session: Session, user: User) -> None:
    """The "confirm your email" message for a new (or re-sent) account sign-up."""
    enqueue(
        session,
        # A random part, so "send it again" is a new email, even twice in one second.
        # (Abuse is limited by the endpoint's rate limit and the per-recipient daily cap.)
        key=f"verify-account:{user.id}:{secrets.token_hex(8)}",
        kind="verify_account",
        to=user.email,
        context={"name": user.name, "verify_url": verify_url(make_token(user.email))},
        reply_to=_reply_to(),
    )


# --- helpers ------------------------------------------------------------------------------------------


def _to_customer(session: Session, order: Order, *, key: str, kind: str, **context: Any) -> None:
    """An email about an order, to the address on the order, only if that address is verified."""
    reason = None
    if not is_blocked(order.email) and not is_verified(session, order.email):
        # Recorded (so support can see what we didn't send, and why), but never sent.
        reason = "unverified"
    enqueue(
        session, key=key, kind=kind, to=order.email, context={"order": order_context(order), **context},
        reply_to=_reply_to(), order_id=order.id, suppressed_reason=reason,
    )


def _reply_to() -> str | None:
    # Customers who hit "reply" reach a person, not the unattended orders@ sending address.
    return current_app.config["ADMIN_NOTIFY_EMAIL"]


def order_context(order: Order) -> dict[str, Any]:
    """Everything an order email shows, as plain values (templates never touch the database)."""
    site = current_app.config["FRONTEND_URL"].rstrip("/")
    address = [
        order.customer_name,
        order.shipping_line1,
        order.shipping_line2,
        f"{order.shipping_city}, {' '.join(part for part in (order.shipping_state, order.shipping_postal_code) if part)}",
        order.shipping_country,
    ]
    return {
        "number": order.order_number,
        "first_name": order.customer_name.split()[0] if order.customer_name.strip() else "there",
        "items": [
            {
                "name": item.product_name,
                "variant": f"{item.color} / {item.size}",
                "quantity": item.quantity,
                "line_total": money(item.line_total_cents),
            }
            for item in order.items
        ],
        "subtotal": money(order.subtotal_cents),
        "shipping": "Free" if order.shipping_cents == 0 else money(order.shipping_cents),
        "shipping_method": SHIPPING_LABELS[order.shipping_method],
        "total": money(order.total_cents),
        "address": [line for line in address if line],
        "is_cod": order.payment_method is PaymentMethod.COD,
        "track_url": f"{site}/track?order={order.order_number}",
    }


def money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _long_date(value: date | None) -> str | None:
    return f"{value:%A, %B} {value.day}" if value else None  # "Friday, October 24"
