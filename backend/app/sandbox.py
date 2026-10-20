"""The sandbox's hosted payment page logic: show a session, take a test card, send the webhook.

Test cards (same numbers Stripe uses, so the habits carry over):
    4242 4242 4242 4242  → payment succeeds
    4000 0000 0000 0002  → card declined
    anything else        → "use a test card"
"""

import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.checkout import CURRENCY, SHIPPING_NAMES, success_url
from app.errors import APIError
from app.models import Order, OrderStatus, PaymentMethod
from app.payments import SandboxProvider, get_provider

SUCCESS_CARD = "4242424242424242"
DECLINE_CARD = "4000000000000002"


class SandboxPayBody(BaseModel):
    card_number: str = Field(min_length=1, max_length=30)
    expiry: str = Field(pattern=r"^\s*(0[1-9]|1[0-2])\s*/\s*\d{2}\s*$")  # MM/YY
    cvc: str = Field(pattern=r"^\d{3,4}$")
    name: str = Field(min_length=1, max_length=120)


def require_sandbox() -> SandboxProvider:
    """Sandbox endpoints exist only while the sandbox is the active provider."""
    provider = get_provider()
    if not isinstance(provider, SandboxProvider):
        raise APIError("not_found", "Not found.", 404)
    return provider


def _find_order(session: Session, session_id: str) -> Order:
    order = session.scalars(
        select(Order)
        # COD orders keep their confirmation token in the same column: never a sandbox payment page.
        .where(Order.stripe_session_id == session_id, Order.payment_method == PaymentMethod.CARD)
        .options(selectinload(Order.items))
    ).one_or_none()
    if order is None or not session_id.startswith("cs_sandbox_"):
        raise APIError("session_not_found", "This payment link is not valid.", 404)
    return order


def _expires_at(order: Order) -> datetime:
    return order.created_at + timedelta(minutes=current_app.config["CHECKOUT_SESSION_MINUTES"])


def _session_status(order: Order) -> str:
    if order.status is OrderStatus.PENDING_PAYMENT:
        return "expired" if datetime.now(UTC) >= _expires_at(order) else "open"
    return "expired" if order.status is OrderStatus.CANCELLED and not order.stripe_payment_intent else "complete"


def session_view(session: Session, session_id: str) -> dict[str, Any]:
    """What the payment page shows. Like Stripe's page: amounts, not addresses."""
    order = _find_order(session, session_id)
    return {
        "session_id": session_id,
        "status": _session_status(order),
        "order_number": order.order_number,
        "email": order.email,
        "currency": CURRENCY,
        "line_items": [
            {"name": f"{item.product_name} — {item.color} / {item.size}", "quantity": item.quantity,
             "amount_cents": item.line_total_cents}
            for item in order.items
        ],
        "shipping": {"name": SHIPPING_NAMES[order.shipping_method], "amount_cents": order.shipping_cents},
        "amount_total_cents": order.total_cents,
        "expires_at": _expires_at(order).isoformat(),
        "success_url": success_url(order.order_number, session_id),
    }


def pay(session: Session, session_id: str, body: SandboxPayBody) -> dict[str, str]:
    provider = require_sandbox()
    order = _find_order(session, session_id)
    status = _session_status(order)

    if status == "complete":
        raise APIError("already_paid", "This order has already been paid.", 409)
    if status == "expired":
        if order.status is OrderStatus.PENDING_PAYMENT:
            _deliver(provider, _event("checkout.session.expired", order, session_id, paid=False))
        raise APIError("session_expired", "This payment page has expired. Please check out again.", 410)

    card = re.sub(r"[\s-]", "", body.card_number)
    if card == DECLINE_CARD:
        # Like Stripe Checkout: a decline sends no webhook; the order simply stays unpaid.
        raise APIError("card_declined", "Your card was declined. Try another card.", 402)
    if card != SUCCESS_CARD:
        raise APIError("use_test_card", "This is a sandbox: use test card 4242 4242 4242 4242.", 400)

    outcome = _deliver(provider, _event("checkout.session.completed", order, session_id, paid=True))
    current_app.logger.info("Sandbox payment for %s: %s", order.order_number, outcome)
    # Even "cancelled_refunded" (sold out meanwhile) goes to the success page, which explains it.
    return {"redirect_url": success_url(order.order_number, session_id)}


def _event(event_type: str, order: Order, session_id: str, *, paid: bool) -> dict[str, Any]:
    """An event shaped exactly like Stripe's, so the same webhook handler processes it."""
    return {
        "id": f"evt_sandbox_{secrets.token_hex(12)}",
        "object": "event",
        "type": event_type,
        "created": int(datetime.now(UTC).timestamp()),
        "data": {
            "object": {
                "id": session_id,
                "object": "checkout.session",
                "payment_status": "paid" if paid else "unpaid",
                "status": "complete" if paid else "expired",
                "amount_total": order.total_cents,
                "currency": CURRENCY,
                "payment_intent": f"pi_sandbox_{secrets.token_hex(12)}" if paid else None,
                "customer_email": order.email,
                "metadata": {"order_id": str(order.id), "order_number": order.order_number},
            }
        },
    }


def _deliver(provider: SandboxProvider, event: dict[str, Any]) -> str:
    """Send ourselves the signed webhook, through the full HTTP stack but in-process.

    A real HTTP request to our own URL could hang forever with one gunicorn worker: the worker
    would wait for a reply only it can give. Flask's test client runs the request in-process
    through routing, signature verification and the webhook handler, exactly like the real thing.
    """
    payload = json.dumps(event).encode()
    response = current_app.test_client().post(
        "/api/sandbox/webhook",
        data=payload,
        headers={provider.signature_header: provider.sign(payload), "Content-Type": "application/json"},
    )
    if response.status_code != 200:
        raise APIError("payment_provider_error", "The sandbox couldn't confirm this payment. Please try again.", 502)
    return str(response.get_json()["outcome"])
