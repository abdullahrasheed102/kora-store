"""Checkout and payment: create orders, start a hosted payment page, and handle payment webhooks.

Card orders work with any PaymentProvider (app/payments): Stripe or our sandbox.
Cash-on-delivery orders need no provider at all (create_cod_order).

The order lifecycle around payment:

    create_cod_order()         order = processing + unpaid; stock taken NOW, in this transaction
                               (the cash arrives later: an admin marks it collected)

    create_checkout()          order = pending_payment, no stock taken, payment session created
         │
         ├── webhook: checkout.session.completed (paid)
         │       └── fulfil(): lock rows, take stock -> processing
         │                     (or, if sold out meanwhile: cancel + full refund)
         │
         └── webhook: checkout.session.expired   (or `flask orders expire-unpaid`)
                 └── cancel: the shopper never paid
"""

import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app import notifications, payments
from app.accounts import AddressBody
from app.errors import APIError
from app.models import (
    EventActor,
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    ProductVariant,
    ShippingMethod,
    StripeEvent,
    User,
)
from app.payments import SESSION_ID_PLACEHOLDER, CheckoutRequest, LineItem
from app.pricing import MAX_CART_LINES, CartLine, quote_cart

log = logging.getLogger(__name__)

CURRENCY = "usd"
SHIPPING_NAMES = {
    ShippingMethod.STANDARD: "Standard shipping (3–6 business days)",
    ShippingMethod.EXPRESS: "Express shipping (2 business days)",
    ShippingMethod.INTERNATIONAL: "International shipping (7–14 business days)",
}


# Digits with optional spaces, dashes, dots, brackets and a leading +. 7-15 digits (the E.164 maximum).
PHONE_PATTERN = re.compile(r"^\+?[0-9 ().-]{7,25}$")


class CheckoutBody(BaseModel):
    email: EmailStr | None = Field(None, max_length=254)  # required for guests; ignored when logged in
    address: AddressBody  # address.name is the recipient's name
    shipping_method: ShippingMethod
    items: list[CartLine] = Field(min_length=1, max_length=MAX_CART_LINES)
    save_address: bool = False
    phone: str | None = Field(None, max_length=30)  # optional for card; required for cash on delivery

    @model_validator(mode="after")
    def _method_matches_country(self) -> "CheckoutBody":
        # Shipping policy: standard/express inside the US; UK, Canada, Australia use international.
        domestic = self.address.country == "US"
        if domestic and self.shipping_method is ShippingMethod.INTERNATIONAL:
            raise ValueError("international shipping is only for addresses outside the US")
        if not domestic and self.shipping_method is not ShippingMethod.INTERNATIONAL:
            raise ValueError("addresses outside the US must use international shipping")
        if self.phone is not None:
            self.phone = self.phone.strip() or None
        if self.phone and not _valid_phone(self.phone):
            raise ValueError("enter a phone number with 7 to 15 digits")
        return self


class CodCheckoutBody(CheckoutBody):
    """Cash on delivery: a phone number is required, and only for US addresses."""

    @model_validator(mode="after")
    def _cod_rules(self) -> "CodCheckoutBody":
        if not self.phone:
            raise ValueError("a phone number is required for cash on delivery")
        if self.address.country != "US":
            # Couriers abroad don't collect cash for us, so COD is offered for US orders only.
            raise ValueError("cash on delivery is only available for US addresses")
        return self


def _valid_phone(phone: str) -> bool:
    digits = sum(character.isdigit() for character in phone)
    return bool(PHONE_PATTERN.match(phone)) and 7 <= digits <= 15


# --- starting checkout -------------------------------------------------------------------------


ADMIN_CANNOT_ORDER = "Admin accounts can't place orders. Log in with a customer account to test checkout."


def _new_order(
    session: Session, body: CheckoutBody, user: User | None, *, method: PaymentMethod
) -> tuple[Order, dict[str, Any]]:
    """Checks shared by both payment methods, and the order built from a fresh server-side quote."""
    if user is not None and user.is_admin:
        # Enforced here, not only by hiding the checkout form: a request sent by hand gets the same answer.
        # (Staff orders would muddle revenue stats and the audit trail; admins test with a customer account.)
        raise APIError("admin_cannot_order", ADMIN_CANNOT_ORDER, 403)
    email = user.email if user else body.email
    if not email:
        raise APIError("validation_error", "email: an email address is required to check out", 400)

    # Re-price everything on the server, exactly as the cart did.
    quote = quote_cart(session, [(line.variant_id, line.quantity) for line in body.items], body.shipping_method)
    if quote["has_issues"]:
        raise APIError("cart_changed", "Some items in your bag changed (price or stock). Please review your bag.", 409)

    address = body.address
    order = Order(
        user_id=user.id if user else None,
        email=email,
        customer_name=address.name,
        phone=body.phone,
        payment_method=method,
        payment_status=PaymentStatus.UNPAID,
        status=OrderStatus.PENDING_PAYMENT,
        subtotal_cents=quote["subtotal_cents"],
        shipping_cents=quote["shipping_cents"],
        total_cents=quote["total_cents"],
        shipping_method=body.shipping_method,
        shipping_line1=address.line1,
        shipping_line2=address.line2,
        shipping_city=address.city,
        shipping_state=address.state,
        shipping_postal_code=address.postal_code,
        shipping_country=address.country,
        items=[
            OrderItem(
                variant_id=item["variant_id"],
                product_name=item["product_name"],
                size=item["size"],
                color=item["color"],
                unit_price_cents=item["unit_price_cents"],
                quantity=item["quantity"],
                is_final_sale=item["is_final_sale"],
            )
            for item in quote["items"]
        ],
    )
    return order, quote


def create_checkout(session: Session, body: CheckoutBody, user: User | None) -> dict[str, Any]:
    """Card: a pending order and a hosted payment page. Stock is taken later, by the webhook."""
    order, quote = _new_order(session, body, user, method=PaymentMethod.CARD)
    order.events = [OrderEvent(status=OrderStatus.PENDING_PAYMENT, note="Checkout started.")]
    session.add(order)
    session.flush()  # gives us order.id and the KO-#### number from the database sequence

    provider = payments.get_provider()
    try:
        checkout_session = provider.create_checkout_session(_checkout_request(order, quote))
    except APIError:
        session.rollback()
        raise
    except Exception as error:  # network error, provider outage, bad request...
        session.rollback()  # no payment session means no order
        log.exception("%s checkout session failed", provider.name)
        raise APIError("payment_provider_error", "We couldn't reach our payment provider. Please try again.", 502) from error

    # (The column is named after Stripe, but it holds the session id for whichever provider.)
    order.stripe_session_id = checkout_session.id
    session.commit()

    if body.save_address and user:
        _save_address_quietly(session, user, body.address)

    return {"order_number": order.order_number, "checkout_url": checkout_session.url}


def create_cod_order(session: Session, body: CodCheckoutBody, user: User | None) -> dict[str, Any]:
    """Cash on delivery: no payment provider, so the order is confirmed straight away.

    There is no payment to wait for, so stock is RESERVED NOW: we lock the variants and take the
    stock in the same transaction that creates the order (the same locking as the card webhook).
    If anything sold out, nothing is saved and the shopper is asked to review their bag.
    """
    order, _quote = _new_order(session, body, user, method=PaymentMethod.COD)
    variants = _lock_variants(session, [item.variant_id for item in order.items])
    if _short_items(order.items, variants):
        session.rollback()
        raise APIError("cart_changed", "Some items in your bag just sold out. Please review your bag.", 409)
    for item in order.items:
        variants[item.variant_id].stock -= item.quantity  # type: ignore[index]

    order.status = OrderStatus.PROCESSING
    # The thank-you page needs a secret only this buyer gets (order numbers are guessable).
    # Card orders use the provider's session id; COD orders get a random token in the same column.
    token = f"cod_{secrets.token_urlsafe(24)}"
    order.stripe_session_id = token
    order.events = [
        OrderEvent(status=OrderStatus.PROCESSING, note="Order placed. Payment: cash on delivery."),
    ]
    session.add(order)
    session.flush()  # the order id goes into the email's idempotency key
    notifications.order_placed(session, order)
    session.commit()  # order, items, stock, event and email: all or nothing

    if body.save_address and user:
        _save_address_quietly(session, user, body.address)
    return {"order_number": order.order_number, "checkout_url": success_url(order.order_number, token)}


def success_url(order_number: str, session_id: str = SESSION_ID_PLACEHOLDER) -> str:
    # The provider swaps the placeholder for the real session id. Knowing it proves you're the buyer.
    frontend = current_app.config["FRONTEND_URL"].rstrip("/")
    return f"{frontend}/order/success?order={order_number}&session_id={session_id}"


def _checkout_request(order: Order, quote: dict[str, Any]) -> CheckoutRequest:
    """The provider-neutral description of what to charge. Each provider adapts it to its own API."""
    minutes = current_app.config["CHECKOUT_SESSION_MINUTES"]
    return CheckoutRequest(
        order_id=order.id,
        order_number=order.order_number,
        email=order.email,
        currency=CURRENCY,
        # The provider shows these amounts, but WE computed them: the webhook re-checks the total.
        line_items=[
            LineItem(
                name=f"{item['product_name']} — {item['color']} / {item['size']}",
                unit_amount_cents=item["unit_price_cents"],
                quantity=item["quantity"],
            )
            for item in quote["items"]
        ],
        shipping_name=SHIPPING_NAMES[order.shipping_method],
        shipping_cents=order.shipping_cents,
        total_cents=order.total_cents,
        expires_at=datetime.now(UTC) + timedelta(minutes=minutes),
        success_url=success_url(order.order_number),
        cancel_url=f"{current_app.config['FRONTEND_URL'].rstrip('/')}/checkout?cancelled=1",
        idempotency_key=f"checkout-order-{order.id}",
    )


def _save_address_quietly(session: Session, user: User, address: AddressBody) -> None:
    from app.accounts import create_address  # local import: accounts imports nothing from here

    try:
        create_address(session, user, address.model_copy(update={"is_default": False}))
    except APIError:
        session.rollback()  # e.g. already 10 saved addresses; checkout itself still worked


# --- webhooks ----------------------------------------------------------------------------------

FULFIL_EVENTS = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
CANCEL_EVENTS = {"checkout.session.expired", "checkout.session.async_payment_failed"}


def handle_payment_event(session: Session, event: dict[str, Any]) -> str:
    """Process one verified payment event (Stripe's shape, from any provider).

    Returns a short outcome label (for logs and tests). Safe to call many times with the same
    event: that's what idempotent means here.
    """
    event_type = event["type"]
    if event_type not in FULFIL_EVENTS | CANCEL_EVENTS:
        return "ignored"

    # Layer 1 of idempotency: remember the event id, in the SAME transaction as the work.
    # (The table is called stripe_events, but it records events from every provider.)
    if session.get(StripeEvent, event["id"]):
        return "duplicate"
    session.add(StripeEvent(id=event["id"], type=event_type))
    try:
        session.flush()  # a concurrent delivery of the same event waits here, then fails
    except IntegrityError:
        session.rollback()
        return "duplicate"

    checkout_session = event["data"]["object"]
    order = _lock_order(session, checkout_session)
    if order is None:
        session.commit()
        log.warning("Stripe event %s for an unknown order", event["id"])
        return "unknown_order"

    if event_type in CANCEL_EVENTS:
        return _cancel_unpaid(session, order, "Checkout expired before payment was completed.")
    if checkout_session.get("payment_status") != "paid":
        session.commit()  # e.g. a delayed payment method: wait for async_payment_succeeded
        return "awaiting_payment"
    return _fulfil(session, order, checkout_session)


def _lock_order(session: Session, checkout_session: dict[str, Any]) -> Order | None:
    """Load the order with a row lock (SELECT ... FOR UPDATE).

    Until this transaction ends, any other webhook for the same order waits here. That's
    layer 2 of idempotency: the second one then sees the order is no longer pending.
    """
    order_id = (checkout_session.get("metadata") or {}).get("order_id")
    condition = (
        Order.id == int(order_id) if order_id else Order.stripe_session_id == checkout_session.get("id")
    )
    return session.scalars(
        select(Order).where(condition).options(selectinload(Order.items)).with_for_update(of=Order)
    ).one_or_none()


def _fulfil(session: Session, order: Order, checkout_session: dict[str, Any]) -> str:
    payment_intent = checkout_session.get("payment_intent")

    if order.status is not OrderStatus.PENDING_PAYMENT:
        if order.status is OrderStatus.CANCELLED and order.stripe_payment_intent is None and payment_intent:
            # Paid after we had already cancelled it as expired: give the money back.
            order.stripe_payment_intent = payment_intent
            return _cancel_and_refund(session, order, "Payment arrived after the order had expired. Refunded in full.")
        session.commit()
        return "already_processed"

    order.stripe_payment_intent = payment_intent

    # Never trust that the amount paid is the amount we expected.
    if checkout_session.get("amount_total") != order.total_cents or checkout_session.get("currency") != CURRENCY:
        log.error("Order %s: paid %s %s, expected %s", order.order_number, checkout_session.get("amount_total"),
                  checkout_session.get("currency"), order.total_cents)
        return _cancel_and_refund(session, order, "Payment amount did not match the order. Refunded in full.")

    variants = _lock_variants(session, [item.variant_id for item in order.items])
    short = _short_items(order.items, variants)
    if short:
        # Someone else bought the last ones while this shopper was paying. We take stock only
        # after payment (no reservations), so this rare case is handled with a full refund.
        return _cancel_and_refund(
            session, order, f"Sold out while you were paying: {', '.join(short)}. Refunded in full."
        )

    for item in order.items:
        variants[item.variant_id].stock -= item.quantity  # type: ignore[index]
    order.status = OrderStatus.PROCESSING
    order.payment_status = PaymentStatus.PAID
    order.status_note = None
    order.events.append(OrderEvent(status=OrderStatus.PROCESSING, note="Payment received."))
    notifications.order_placed(session, order)  # an outbox row, saved (or not) with everything else
    session.commit()  # stock, status, event, email and the StripeEvent row: all or nothing
    return "fulfilled"


def _lock_variants(session: Session, variant_ids: list[int | None]) -> dict[int, ProductVariant]:
    """Lock these variant rows (SELECT ... FOR UPDATE) until the transaction ends, ALWAYS in id
    order. If two checkouts locked the same rows in different orders, each could wait for the
    other forever (a deadlock). Used by the card webhook and by cash on delivery."""
    ids = sorted({variant_id for variant_id in variant_ids if variant_id is not None})
    return {
        variant.id: variant
        for variant in session.scalars(
            select(ProductVariant).where(ProductVariant.id.in_(ids)).order_by(ProductVariant.id).with_for_update()
        )
    }


def _short_items(items: list[OrderItem], variants: dict[int, ProductVariant]) -> list[str]:
    """Names of items we can't fully supply right now (deleted variant or not enough stock)."""
    return [
        item.product_name
        for item in items
        if item.variant_id not in variants or variants[item.variant_id].stock < item.quantity
    ]


def _cancel_and_refund(session: Session, order: Order, note: str) -> str:
    order.status = OrderStatus.CANCELLED
    order.status_note = note
    order.events.append(OrderEvent(status=OrderStatus.CANCELLED, note=note))
    session.commit()  # release the row locks BEFORE the slow network call to Stripe

    if order.stripe_payment_intent:
        try:
            payments.get_provider().refund_payment(order.stripe_payment_intent, idempotency_key=f"refund-order-{order.id}")
        except Exception:
            log.exception("Refund failed for order %s", order.order_number)
            order.status_note = f"{note} (Automatic refund failed: needs a manual refund.)"
            session.commit()
            return "cancelled_refund_failed"
        order.payment_status = PaymentStatus.REFUNDED
        session.commit()
    return "cancelled_refunded"


def _cancel_unpaid(session: Session, order: Order, note: str) -> str:
    if order.status is not OrderStatus.PENDING_PAYMENT:
        session.commit()  # already paid or already cancelled: nothing to do
        return "already_processed"
    order.status = OrderStatus.CANCELLED
    order.status_note = note
    order.events.append(OrderEvent(status=OrderStatus.CANCELLED, note=note))
    session.commit()
    return "expired"


# --- safety net for missed webhooks -------------------------------------------------------------


def expire_unpaid_orders(session: Session, older_than: timedelta, now: datetime | None = None) -> list[str]:
    """Cancel pending_payment orders older than `older_than`. Returns their order numbers.

    Run it on a schedule (e.g. every 15 minutes). Use a cut-off longer than the Stripe session
    lifetime (30 min): after that, Stripe can no longer take a payment for these orders.
    """
    cutoff = (now or datetime.now(UTC)) - older_than
    orders = session.scalars(
        select(Order)
        .where(Order.status == OrderStatus.PENDING_PAYMENT, Order.created_at < cutoff)
        # SKIP LOCKED: if a webhook is processing an order right now, leave it alone.
        .with_for_update(skip_locked=True)
    ).all()
    for order in orders:
        order.status = OrderStatus.CANCELLED
        order.status_note = "Checkout expired before payment was completed."
        order.events.append(
            OrderEvent(status=OrderStatus.CANCELLED, note=order.status_note, created_by=EventActor.SYSTEM)
        )
    session.commit()
    return [order.order_number for order in orders]


# --- confirmation page --------------------------------------------------------------------------


def get_confirmation(session: Session, order_number: str, stripe_session_id: str) -> Order:
    """The order for the thank-you page. Both the number AND the Stripe session id must match:
    order numbers are guessable (KO-1013, KO-1014...), the session id is a secret only the buyer
    received in their redirect URL."""
    order = session.scalars(
        select(Order)
        .where(Order.order_number == order_number.upper(), Order.stripe_session_id == stripe_session_id)
        .options(selectinload(Order.items), selectinload(Order.events))
    ).one_or_none()
    if order is None:
        raise APIError("order_not_found", "Order not found.", 404)
    return order
