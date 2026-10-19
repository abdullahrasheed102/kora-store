"""Checkout sessions, Stripe webhooks, stock under concurrency, expiry, and the confirmation page."""

import threading
from datetime import timedelta
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.checkout import expire_unpaid_orders
from app.models import Order, OrderStatus, ProductVariant, StripeEvent, User
from app.seed import SeedCounts
from app.payments import StripeProvider
from tests.conftest import FakeStripe, csrf_headers, send_stripe_event

_ORIGINAL_CREATE_SESSION = StripeProvider._create_session

ADDRESS = {"name": "Ayesha Khan", "line1": "12 Garden Road", "city": "Austin", "state": "TX", "postal_code": "78701", "country": "US"}


def variant(session: Session, sku: str) -> ProductVariant:
    return session.scalars(select(ProductVariant).where(ProductVariant.sku == sku)).one()


def checkout_body(items: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    return {"email": "buyer@example.com", "address": ADDRESS, "shipping_method": "standard", "items": items, **overrides}


def start_checkout(client: FlaskClient, items: list[dict[str, Any]], status: int = 201, **overrides: Any) -> Any:
    response = client.post("/api/checkout/session", json=checkout_body(items, **overrides))
    assert response.status_code == status, response.get_json()
    return response.get_json()


def get_order(session: Session, number: str) -> Order:
    session.expire_all()  # webhooks ran in other requests; read fresh rows
    return session.scalars(select(Order).where(Order.order_number == number)).one()


def completed_event(order: Order, event_id: str = "evt_1", **overrides: Any) -> dict[str, Any]:
    session_object = {
        "id": order.stripe_session_id,
        "object": "checkout.session",
        "payment_status": "paid",
        "amount_total": order.total_cents,
        "currency": "usd",
        "payment_intent": f"pi_{order.order_number}",
        "metadata": {"order_id": str(order.id), "order_number": order.order_number},
        **overrides,
    }
    return {"id": event_id, "type": "checkout.session.completed", "data": {"object": session_object}}


@pytest.fixture
def tee(db_session: Session, seeded: SeedCounts) -> ProductVariant:
    return variant(db_session, "KO-001-WHIT-M")  # $24, stock 25


# --- creating a checkout session --------------------------------------------------------------


def test_checkout_creates_pending_order_and_stripe_session(
    client: FlaskClient, db_session: Session, fake_stripe: FakeStripe, tee: ProductVariant
) -> None:
    body = start_checkout(client, [{"variant_id": tee.id, "quantity": 2, "price_cents": 1}])

    assert body["order_number"] == "KO-1013"
    assert body["checkout_url"] == "https://checkout.stripe.test/c/pay/cs_test_1"

    order = get_order(db_session, "KO-1013")
    assert order.status is OrderStatus.PENDING_PAYMENT
    assert (order.subtotal_cents, order.shipping_cents, order.total_cents) == (4800, 695, 5495)  # client price ignored
    assert order.stripe_session_id == "cs_test_1"
    assert [event.status for event in order.events] == [OrderStatus.PENDING_PAYMENT]
    assert variant(db_session, "KO-001-WHIT-M").stock == 25  # stock is NOT taken before payment

    params = fake_stripe.sessions[0]["params"]
    assert params["line_items"][0]["price_data"]["unit_amount"] == 2400
    assert params["line_items"][0]["quantity"] == 2
    assert params["shipping_options"][0]["shipping_rate_data"]["fixed_amount"]["amount"] == 695
    assert params["metadata"] == {"order_id": str(order.id), "order_number": "KO-1013"}
    assert "{CHECKOUT_SESSION_ID}" in params["success_url"] and "order=KO-1013" in params["success_url"]
    assert fake_stripe.sessions[0]["idempotency_key"] == f"checkout-order-{order.id}"


def test_session_expires_after_30_minutes(client: FlaskClient, fake_stripe: FakeStripe, tee: ProductVariant) -> None:
    import time

    start_checkout(client, [{"variant_id": tee.id, "quantity": 1}])
    expires_in = fake_stripe.sessions[0]["params"]["expires_at"] - time.time()
    assert 29 * 60 < expires_in <= 30 * 60


def test_guest_needs_an_email(client: FlaskClient, fake_stripe: FakeStripe, tee: ProductVariant) -> None:
    body = start_checkout(client, [{"variant_id": tee.id, "quantity": 1}], status=400, email=None)
    assert "email" in body["error"]["message"]


def test_logged_in_checkout_uses_the_account(
    logged_in: FlaskClient, db_session: Session, fake_stripe: FakeStripe, customer: User, tee: ProductVariant
) -> None:
    response = logged_in.post(
        "/api/checkout/session",
        json=checkout_body([{"variant_id": tee.id, "quantity": 1}], email="someone-else@example.com", save_address=True),
        headers=csrf_headers(logged_in),
    )
    assert response.status_code == 201
    order = get_order(db_session, response.get_json()["order_number"])
    assert order.user_id == customer.id
    assert order.email == customer.email  # the account's email, not one typed into the form
    assert len(customer.addresses) == 1  # "save this address" worked


def test_logged_in_checkout_needs_csrf_header(logged_in: FlaskClient, fake_stripe: FakeStripe, tee: ProductVariant) -> None:
    response = logged_in.post("/api/checkout/session", json=checkout_body([{"variant_id": tee.id, "quantity": 1}]))
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("country", "method"),
    [("US", "international"), ("GB", "standard"), ("CA", "express")],
)
def test_shipping_method_must_match_country(
    client: FlaskClient, fake_stripe: FakeStripe, tee: ProductVariant, country: str, method: str
) -> None:
    address = {**ADDRESS, "country": country, "state": None if country != "US" else "TX"}
    start_checkout(client, [{"variant_id": tee.id, "quantity": 1}], status=400, address=address, shipping_method=method)


def test_international_order(client: FlaskClient, db_session: Session, fake_stripe: FakeStripe, tee: ProductVariant) -> None:
    address = {"name": "Sam", "line1": "10 High St", "city": "London", "postal_code": "N1 9GU", "country": "GB"}
    body = start_checkout(client, [{"variant_id": tee.id, "quantity": 4}], address=address, shipping_method="international")
    assert get_order(db_session, body["order_number"]).shipping_cents == 1995  # no free shipping abroad


def test_changed_cart_is_refused(client: FlaskClient, db_session: Session, fake_stripe: FakeStripe, tee: ProductVariant) -> None:
    tee.stock = 1
    db_session.commit()
    body = start_checkout(client, [{"variant_id": tee.id, "quantity": 3}], status=409)
    assert body["error"]["code"] == "cart_changed"
    assert fake_stripe.sessions == []


def test_empty_cart_is_refused(client: FlaskClient, fake_stripe: FakeStripe, seeded: SeedCounts) -> None:
    start_checkout(client, [], status=400)


def test_stripe_outage_leaves_no_order(client: FlaskClient, db_session: Session, fake_stripe: FakeStripe, tee: ProductVariant) -> None:
    fake_stripe.fail_checkout = True
    body = start_checkout(client, [{"variant_id": tee.id, "quantity": 1}], status=502)
    assert body["error"]["code"] == "payment_provider_error"
    assert db_session.scalars(select(Order).where(Order.status == OrderStatus.PENDING_PAYMENT)).all() == []


def test_payments_not_configured(
    app: Flask, client: FlaskClient, fake_stripe: FakeStripe, tee: ProductVariant, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.config["STRIPE_SECRET_KEY"] = ""
    monkeypatch.setattr(StripeProvider, "_create_session", _ORIGINAL_CREATE_SESSION)  # the real call notices
    body = start_checkout(client, [{"variant_id": tee.id, "quantity": 1}], status=503)
    assert body["error"]["code"] == "payments_not_configured"


# --- webhook signatures -------------------------------------------------------------------------


def test_webhook_rejects_a_bad_signature(client: FlaskClient, db_session: Session, fake_stripe: FakeStripe) -> None:
    response = send_stripe_event(client, {"id": "evt_x", "type": "checkout.session.completed"}, secret="whsec_wrong")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_signature"


def test_webhook_rejects_a_missing_signature(client: FlaskClient, db_session: Session, fake_stripe: FakeStripe) -> None:
    response = client.post("/api/stripe/webhook", data="{}", content_type="application/json")
    assert response.status_code == 400


def test_webhook_rejects_an_old_replayed_event(client: FlaskClient, db_session: Session, fake_stripe: FakeStripe) -> None:
    import time

    response = send_stripe_event(client, {"id": "evt_x", "type": "x"}, timestamp=int(time.time()) - 600)
    assert response.status_code == 400


def test_unhandled_event_types_are_acknowledged(client: FlaskClient, db_session: Session, fake_stripe: FakeStripe) -> None:
    response = send_stripe_event(client, {"id": "evt_x", "type": "customer.created", "data": {"object": {}}})
    assert response.status_code == 200
    assert response.get_json()["outcome"] == "ignored"


# --- fulfilment ---------------------------------------------------------------------------------


@pytest.fixture
def pending_order(client: FlaskClient, db_session: Session, fake_stripe: FakeStripe, tee: ProductVariant) -> Order:
    number = start_checkout(client, [{"variant_id": tee.id, "quantity": 2}])["order_number"]
    return get_order(db_session, number)


def test_paid_webhook_takes_stock_and_marks_processing(client: FlaskClient, db_session: Session, pending_order: Order) -> None:
    response = send_stripe_event(client, completed_event(pending_order))
    assert response.get_json()["outcome"] == "fulfilled"

    order = get_order(db_session, pending_order.order_number)
    assert order.status is OrderStatus.PROCESSING
    assert order.stripe_payment_intent == f"pi_{order.order_number}"
    assert [event.status for event in order.events] == [OrderStatus.PENDING_PAYMENT, OrderStatus.PROCESSING]
    assert variant(db_session, "KO-001-WHIT-M").stock == 23


def test_same_event_twice_takes_stock_once(client: FlaskClient, db_session: Session, pending_order: Order) -> None:
    event = completed_event(pending_order)
    assert send_stripe_event(client, event).get_json()["outcome"] == "fulfilled"
    assert send_stripe_event(client, event).get_json()["outcome"] == "duplicate"
    assert variant(db_session, "KO-001-WHIT-M").stock == 23
    assert db_session.scalar(select(StripeEvent.id)) == "evt_1"


def test_two_different_events_for_one_order_take_stock_once(client: FlaskClient, db_session: Session, pending_order: Order) -> None:
    send_stripe_event(client, completed_event(pending_order, "evt_1"))
    second = completed_event(pending_order, "evt_2")
    second["type"] = "checkout.session.async_payment_succeeded"
    assert send_stripe_event(client, second).get_json()["outcome"] == "already_processed"
    assert variant(db_session, "KO-001-WHIT-M").stock == 23


def test_unpaid_completion_waits(client: FlaskClient, db_session: Session, pending_order: Order) -> None:
    response = send_stripe_event(client, completed_event(pending_order, payment_status="unpaid"))
    assert response.get_json()["outcome"] == "awaiting_payment"
    assert get_order(db_session, pending_order.order_number).status is OrderStatus.PENDING_PAYMENT


def test_sold_out_while_paying_cancels_and_refunds(
    client: FlaskClient, db_session: Session, pending_order: Order, fake_stripe: FakeStripe
) -> None:
    variant(db_session, "KO-001-WHIT-M").stock = 1  # someone bought them meanwhile
    db_session.commit()

    assert send_stripe_event(client, completed_event(pending_order)).get_json()["outcome"] == "cancelled_refunded"
    order = get_order(db_session, pending_order.order_number)
    assert order.status is OrderStatus.CANCELLED
    assert "Sold out while you were paying" in (order.status_note or "")
    assert fake_stripe.refunds == [f"pi_{order.order_number}"]
    assert variant(db_session, "KO-001-WHIT-M").stock == 1  # untouched, never negative


def test_wrong_amount_cancels_and_refunds(client: FlaskClient, db_session: Session, pending_order: Order, fake_stripe: FakeStripe) -> None:
    outcome = send_stripe_event(client, completed_event(pending_order, amount_total=100)).get_json()["outcome"]
    assert outcome == "cancelled_refunded"
    assert fake_stripe.refunds and variant(db_session, "KO-001-WHIT-M").stock == 25


def test_failed_refund_is_recorded_for_a_human(
    client: FlaskClient, db_session: Session, pending_order: Order, fake_stripe: FakeStripe
) -> None:
    fake_stripe.fail_refund = True
    variant(db_session, "KO-001-WHIT-M").stock = 0
    db_session.commit()
    response = send_stripe_event(client, completed_event(pending_order))
    assert response.status_code == 200
    assert response.get_json()["outcome"] == "cancelled_refund_failed"
    assert "needs a manual refund" in (get_order(db_session, pending_order.order_number).status_note or "")


def test_unknown_order_is_acknowledged(client: FlaskClient, db_session: Session, pending_order: Order) -> None:
    event = completed_event(pending_order, metadata={"order_id": "999999"})
    assert send_stripe_event(client, event).get_json()["outcome"] == "unknown_order"


# --- concurrency: the last item ----------------------------------------------------------------


def test_two_payments_for_the_last_item_sell_it_once(
    app: Flask, db_session: Session, fake_stripe: FakeStripe, tee: ProductVariant
) -> None:
    tee.stock = 1
    db_session.commit()
    client = app.test_client()
    numbers = [start_checkout(client, [{"variant_id": tee.id, "quantity": 1}])["order_number"] for _ in range(2)]
    events = [completed_event(get_order(db_session, n), f"evt_{n}") for n in numbers]
    db_session.rollback()  # end our own transaction so we don't hold anything open

    # Both webhooks arrive at the same moment, each in its own thread, request and DB connection.
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def deliver(event: dict[str, Any]) -> None:
        barrier.wait()
        outcomes.append(send_stripe_event(app.test_client(), event).get_json()["outcome"])

    threads = [threading.Thread(target=deliver, args=(event,)) for event in events]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    # Without the row lock both would read stock=1, both would write 0, and we'd oversell.
    assert sorted(outcomes) == ["cancelled_refunded", "fulfilled"]
    assert variant(db_session, "KO-001-WHIT-M").stock == 0
    statuses = sorted(get_order(db_session, n).status.value for n in numbers)
    assert statuses == ["cancelled", "processing"]


# --- expiry -------------------------------------------------------------------------------------


def test_expired_session_cancels_the_order(client: FlaskClient, db_session: Session, pending_order: Order) -> None:
    event = completed_event(pending_order, "evt_exp")
    event["type"] = "checkout.session.expired"
    assert send_stripe_event(client, event).get_json()["outcome"] == "expired"
    order = get_order(db_session, pending_order.order_number)
    assert order.status is OrderStatus.CANCELLED
    assert variant(db_session, "KO-001-WHIT-M").stock == 25


def test_expiry_does_not_touch_a_paid_order(client: FlaskClient, db_session: Session, pending_order: Order) -> None:
    send_stripe_event(client, completed_event(pending_order))
    event = completed_event(pending_order, "evt_exp")
    event["type"] = "checkout.session.expired"
    assert send_stripe_event(client, event).get_json()["outcome"] == "already_processed"
    assert get_order(db_session, pending_order.order_number).status is OrderStatus.PROCESSING


def test_payment_after_expiry_is_refunded(
    client: FlaskClient, db_session: Session, pending_order: Order, fake_stripe: FakeStripe
) -> None:
    expired = completed_event(pending_order, "evt_exp")
    expired["type"] = "checkout.session.expired"
    send_stripe_event(client, expired)
    assert send_stripe_event(client, completed_event(pending_order, "evt_paid")).get_json()["outcome"] == "cancelled_refunded"
    assert fake_stripe.refunds == [f"pi_{pending_order.order_number}"]
    assert variant(db_session, "KO-001-WHIT-M").stock == 25


def test_expire_unpaid_orders_job(db_session: Session, pending_order: Order) -> None:
    assert expire_unpaid_orders(db_session, timedelta(minutes=60)) == []  # too recent

    pending_order.created_at = pending_order.created_at - timedelta(hours=2)
    db_session.commit()
    assert expire_unpaid_orders(db_session, timedelta(minutes=60)) == [pending_order.order_number]
    order = get_order(db_session, pending_order.order_number)
    assert order.status is OrderStatus.CANCELLED
    assert order.events[-1].status is OrderStatus.CANCELLED


def test_expire_command_refuses_a_cutoff_inside_the_session_lifetime(app: Flask, db_session: Session) -> None:
    result = app.test_cli_runner().invoke(args=["orders", "expire-unpaid", "--older-than", "10"])
    assert result.exit_code != 0


def test_expire_command(app: Flask, db_session: Session) -> None:
    result = app.test_cli_runner().invoke(args=["orders", "expire-unpaid"])
    assert result.exit_code == 0
    assert "Expired 0 unpaid order(s)." in result.output


# --- confirmation page --------------------------------------------------------------------------


def test_confirmation_needs_the_matching_session_id(client: FlaskClient, pending_order: Order) -> None:
    number = pending_order.order_number
    good = client.get(f"/api/orders/{number}/confirmation?session_id={pending_order.stripe_session_id}")
    assert good.status_code == 200
    assert good.get_json()["order_number"] == number
    assert good.headers["Cache-Control"] == "no-store"

    assert client.get(f"/api/orders/{number}/confirmation?session_id=cs_test_guess").status_code == 404
    assert client.get(f"/api/orders/{number}/confirmation").status_code == 404


def test_live_stripe_keys_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import DevelopmentConfig

    for name, value in {"SECRET_KEY": "x", "JWT_SECRET_KEY": "x" * 32, "DATABASE_URL": "postgresql://u:p@h/db",
                        "PAYMENT_PROVIDER": "stripe", "STRIPE_SECRET_KEY": "sk_live_123"}.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match="Live Stripe keys"):
        DevelopmentConfig()


def test_session_params_match_the_stripe_api(client: FlaskClient, fake_stripe: FakeStripe, tee: ProductVariant) -> None:
    """Every top-level parameter we send must exist in the installed Stripe library's schema.

    The fake accepts anything, so without this check a renamed Stripe parameter (as happened
    with payment_method_types) would only fail against the real API.
    """
    from stripe.params.checkout._session_create_params import SessionCreateParams

    start_checkout(client, [{"variant_id": tee.id, "quantity": 1}])
    sent = set(fake_stripe.sessions[0]["params"])
    assert sent <= set(SessionCreateParams.__annotations__), sent - set(SessionCreateParams.__annotations__)
