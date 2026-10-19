"""The sandbox payment provider: hosted page data, test cards, signed webhooks, idempotency."""

import json
import time
from datetime import timedelta
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Order, OrderStatus, ProductVariant, StripeEvent
from app.payments import PROVIDERS, PaymentProvider, SandboxProvider, StripeProvider
from app.sandbox import _event
from app.seed import SeedCounts

ADDRESS = {"name": "Ayesha Khan", "line1": "12 Garden Road", "city": "Austin", "state": "TX", "postal_code": "78701", "country": "US"}
CARD = {"expiry": "12/34", "cvc": "123", "name": "Ayesha Khan"}
SKU = "KO-001-WHIT-M"  # $24, stock 25


def stock(session: Session) -> int:
    session.expire_all()
    return session.scalars(select(ProductVariant.stock).where(ProductVariant.sku == SKU)).one()


def get_order(session: Session, number: str) -> Order:
    session.expire_all()
    return session.scalars(select(Order).where(Order.order_number == number)).one()


@pytest.fixture
def checkout(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> dict[str, Any]:
    """Start a sandbox checkout for 2 tees. Returns the API response plus the session id."""
    variant_id = db_session.scalars(select(ProductVariant.id).where(ProductVariant.sku == SKU)).one()
    response = client.post(
        "/api/checkout/session",
        json={"email": "buyer@example.com", "address": ADDRESS, "shipping_method": "standard",
              "items": [{"variant_id": variant_id, "quantity": 2}]},
    )
    assert response.status_code == 201, response.get_json()
    body = response.get_json()
    body["session_id"] = body["checkout_url"].rsplit("/", 1)[1]
    return body


def pay(client: FlaskClient, session_id: str, card: str) -> Any:
    return client.post(f"/api/sandbox/sessions/{session_id}/pay", json={**CARD, "card_number": card})


def post_webhook(client: FlaskClient, app: Flask, event: dict[str, Any], *, timestamp: int | None = None,
                 secret: str | None = None) -> Any:
    payload = json.dumps(event).encode()
    with app.app_context():
        if secret:
            app.config["SANDBOX_WEBHOOK_SECRET"] = secret  # sign with the wrong key...
        header = SandboxProvider().sign(payload, timestamp)
        app.config["SANDBOX_WEBHOOK_SECRET"] = "sandbox_test_secret"  # ...but verify with the right one
    return client.post("/api/sandbox/webhook", data=payload, content_type="application/json",
                       headers={"Sandbox-Signature": header})


# --- the interface ----------------------------------------------------------------------------


def test_both_providers_implement_the_interface() -> None:
    assert set(PROVIDERS) == {"sandbox", "stripe"}
    for provider in (SandboxProvider, StripeProvider):
        assert issubclass(provider, PaymentProvider)
        assert not provider.__abstractmethods__  # every abstract method is implemented
        provider()  # an abstract method left out would make this raise TypeError


# --- starting checkout --------------------------------------------------------------------------


def test_checkout_returns_the_sandbox_payment_page(checkout: dict[str, Any], db_session: Session) -> None:
    assert checkout["checkout_url"].startswith("http://localhost:3000/pay/sandbox/cs_sandbox_")
    assert len(checkout["session_id"]) > 40  # long and random: it's the buyer's secret
    order = get_order(db_session, checkout["order_number"])
    assert order.status is OrderStatus.PENDING_PAYMENT
    assert order.stripe_session_id == checkout["session_id"]
    assert stock(db_session) == 25


def test_session_page_data(client: FlaskClient, checkout: dict[str, Any]) -> None:
    body = client.get(f"/api/sandbox/sessions/{checkout['session_id']}").get_json()
    assert body["status"] == "open"
    assert body["amount_total_cents"] == 5495  # 2 x $24 + $6.95
    assert body["line_items"] == [{"name": "Everyday Cotton Tee — White / M", "quantity": 2, "amount_cents": 4800}]
    assert body["shipping"]["amount_cents"] == 695


def test_unknown_session_is_404(client: FlaskClient, db_session: Session) -> None:
    assert client.get("/api/sandbox/sessions/cs_sandbox_nope").status_code == 404


# --- paying -------------------------------------------------------------------------------------


def test_successful_card_fulfils_the_order(client: FlaskClient, db_session: Session, checkout: dict[str, Any]) -> None:
    response = pay(client, checkout["session_id"], "4242 4242 4242 4242")

    assert response.status_code == 200
    assert response.get_json()["redirect_url"] == (
        f"http://localhost:3000/order/success?order={checkout['order_number']}&session_id={checkout['session_id']}"
    )
    order = get_order(db_session, checkout["order_number"])
    assert order.status is OrderStatus.PROCESSING
    assert order.stripe_payment_intent and order.stripe_payment_intent.startswith("pi_sandbox_")
    assert stock(db_session) == 23
    # The webhook went through the normal handler: the event id was recorded for idempotency.
    assert db_session.scalar(select(func.count()).select_from(StripeEvent)) == 1


def test_declined_card_leaves_the_order_unpaid(client: FlaskClient, db_session: Session, checkout: dict[str, Any]) -> None:
    response = pay(client, checkout["session_id"], "4000 0000 0000 0002")

    assert response.status_code == 402
    assert response.get_json()["error"]["code"] == "card_declined"
    assert get_order(db_session, checkout["order_number"]).status is OrderStatus.PENDING_PAYMENT
    assert stock(db_session) == 25
    assert db_session.scalar(select(func.count()).select_from(StripeEvent)) == 0  # no webhook for a decline


def test_other_cards_are_refused(client: FlaskClient, checkout: dict[str, Any]) -> None:
    response = pay(client, checkout["session_id"], "5555 5555 5555 4444")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "use_test_card"


def test_paying_twice_is_refused(client: FlaskClient, db_session: Session, checkout: dict[str, Any]) -> None:
    assert pay(client, checkout["session_id"], "4242424242424242").status_code == 200
    second = pay(client, checkout["session_id"], "4242424242424242")
    assert second.status_code == 409
    assert stock(db_session) == 23


def test_card_form_validation(client: FlaskClient, checkout: dict[str, Any]) -> None:
    for card in ({**CARD, "expiry": "13/30"}, {**CARD, "cvc": "12"}, {**CARD, "name": ""}):
        response = client.post(f"/api/sandbox/sessions/{checkout['session_id']}/pay", json={**card, "card_number": "4242424242424242"})
        assert response.status_code == 400, card


def test_expired_session_cancels_the_order(client: FlaskClient, db_session: Session, checkout: dict[str, Any]) -> None:
    order = get_order(db_session, checkout["order_number"])
    order.created_at = order.created_at - timedelta(minutes=31)
    db_session.commit()

    assert client.get(f"/api/sandbox/sessions/{checkout['session_id']}").get_json()["status"] == "expired"
    response = pay(client, checkout["session_id"], "4242424242424242")
    assert response.status_code == 410
    assert get_order(db_session, checkout["order_number"]).status is OrderStatus.CANCELLED
    assert stock(db_session) == 25


# --- the webhook itself -------------------------------------------------------------------------


def paid_event(app: Flask, db_session: Session, checkout: dict[str, Any]) -> dict[str, Any]:
    with app.app_context():
        return _event("checkout.session.completed", get_order(db_session, checkout["order_number"]),
                      checkout["session_id"], paid=True)


def test_webhook_with_a_valid_signature_is_processed(
    app: Flask, client: FlaskClient, db_session: Session, checkout: dict[str, Any]
) -> None:
    response = post_webhook(client, app, paid_event(app, db_session, checkout))
    assert response.status_code == 200
    assert response.get_json()["outcome"] == "fulfilled"


def test_webhook_signed_with_the_wrong_secret_is_rejected(
    app: Flask, client: FlaskClient, db_session: Session, checkout: dict[str, Any]
) -> None:
    response = post_webhook(client, app, paid_event(app, db_session, checkout), secret="attacker-guess")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_signature"
    assert get_order(db_session, checkout["order_number"]).status is OrderStatus.PENDING_PAYMENT


def test_tampered_body_is_rejected(app: Flask, client: FlaskClient, db_session: Session, checkout: dict[str, Any]) -> None:
    event = paid_event(app, db_session, checkout)
    payload = json.dumps(event).encode()
    with app.app_context():
        header = SandboxProvider().sign(payload)
    tampered = payload.replace(b'"amount_total": 5495', b'"amount_total": 1')  # change one value after signing
    response = client.post("/api/sandbox/webhook", data=tampered, content_type="application/json",
                           headers={"Sandbox-Signature": header})
    assert response.status_code == 400


def test_missing_signature_is_rejected(client: FlaskClient, db_session: Session) -> None:
    assert client.post("/api/sandbox/webhook", data=b"{}", content_type="application/json").status_code == 400


def test_old_timestamp_is_rejected(app: Flask, client: FlaskClient, db_session: Session, checkout: dict[str, Any]) -> None:
    # A genuine, correctly signed event, but from 10 minutes ago: a replay.
    response = post_webhook(client, app, paid_event(app, db_session, checkout), timestamp=int(time.time()) - 600)
    assert response.status_code == 400
    assert "too old" in response.get_json()["error"]["message"]


def test_same_event_twice_takes_stock_once(app: Flask, client: FlaskClient, db_session: Session, checkout: dict[str, Any]) -> None:
    event = paid_event(app, db_session, checkout)
    assert post_webhook(client, app, event).get_json()["outcome"] == "fulfilled"
    assert post_webhook(client, app, event).get_json()["outcome"] == "duplicate"
    assert stock(db_session) == 23


def test_sold_out_while_paying_is_refunded(client: FlaskClient, db_session: Session, checkout: dict[str, Any]) -> None:
    db_session.execute(ProductVariant.__table__.update().where(ProductVariant.sku == SKU).values(stock=1))
    db_session.commit()
    response = pay(client, checkout["session_id"], "4242424242424242")
    assert response.status_code == 200  # still goes to the success page, which explains
    order = get_order(db_session, checkout["order_number"])
    assert order.status is OrderStatus.CANCELLED
    assert "Refunded in full" in (order.status_note or "")
    assert stock(db_session) == 1


# --- only the active provider is reachable -------------------------------------------------------


def test_sandbox_endpoints_are_off_when_stripe_is_active(app: Flask, client: FlaskClient, checkout: dict[str, Any]) -> None:
    app.config["PAYMENT_PROVIDER"] = "stripe"
    assert client.get(f"/api/sandbox/sessions/{checkout['session_id']}").status_code == 404
    assert pay(client, checkout["session_id"], "4242424242424242").status_code == 404
    assert client.post("/api/sandbox/webhook", data=b"{}").status_code == 404


def test_stripe_webhook_is_off_when_sandbox_is_active(client: FlaskClient, db_session: Session) -> None:
    assert client.post("/api/stripe/webhook", data=b"{}").status_code == 404
