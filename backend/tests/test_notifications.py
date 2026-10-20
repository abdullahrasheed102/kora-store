"""Each automatic email (docs/AI_PLAN.md section 4): the right email, to the right person, once."""

import re
from typing import Any

import pytest
from flask.testing import FlaskClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import admin as admin_service
from app import notifications
from app.models import EmailOutbox, EmailStatus, Order, OrderStatus, ProductVariant
from app.payments import SandboxProvider
from app.seed import SeedCounts
from tests.conftest import FIXED_NOW, SHOPPER_EMAIL, FakeStripe, RecordingSender, csrf_headers, send_stripe_event, verify_address
from tests.test_checkout import completed_event, get_order, start_checkout
from tests.test_cod import place_cod

TOKEN = re.compile(r"token=([A-Za-z0-9_.\-]+)")


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_service, "utc_now", lambda: FIXED_NOW)


@pytest.fixture
def no_refunds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SandboxProvider, "refund_payment", lambda *_args, **_kwargs: None)


@pytest.fixture
def tee(db_session: Session, seeded: SeedCounts) -> ProductVariant:
    return db_session.scalars(select(ProductVariant).where(ProductVariant.sku == "KO-001-WHIT-M")).one()


def admin_post(admin: FlaskClient, path: str, body: dict[str, Any]) -> Any:
    response = admin.post(path, json=body, headers=csrf_headers(admin))
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def sendable_order(session: Session, number: str, *, verified: bool = True) -> Order:
    """A seeded order, moved to an address that may receive email (seed orders use @example.com)."""
    order = get_order(session, number)
    order.email = SHOPPER_EMAIL
    session.commit()
    if verified:
        verify_address(session, SHOPPER_EMAIL)
    return order


def outbox_rows(session: Session, kind: str | None = None) -> list[EmailOutbox]:
    session.expire_all()
    stmt = select(EmailOutbox).order_by(EmailOutbox.id)
    if kind:
        stmt = stmt.where(EmailOutbox.kind == kind)
    return list(session.scalars(stmt))


# --- order placed ------------------------------------------------------------------------------


def test_cod_order_to_a_verified_address_gets_the_confirmation(client: FlaskClient, db_session: Session,
                                                               tee: ProductVariant, mailbox: RecordingSender) -> None:
    verify_address(db_session, SHOPPER_EMAIL)
    number = place_cod(client, [{"variant_id": tee.id, "quantity": 2}], email=SHOPPER_EMAIL)["order_number"]

    [email] = mailbox.sent
    assert email.subject == f"Your order {number} is confirmed"
    assert email.to == SHOPPER_EMAIL and email.reply_to == "owner@kora.local"
    assert "Everyday Cotton Tee" in email.text and "cash on delivery" in email.text
    assert f"/track?order={number}" in email.html


def test_unverified_guest_first_confirms_then_gets_the_confirmation_once(
    client: FlaskClient, db_session: Session, tee: ProductVariant, mailbox: RecordingSender
) -> None:
    number = place_cod(client, [{"variant_id": tee.id, "quantity": 1}], email=SHOPPER_EMAIL)["order_number"]

    [ask] = mailbox.sent
    assert ask.subject == f"Confirm your email to get updates on order {number}"
    assert "Everyday Cotton Tee" not in ask.text + ask.html  # says nothing useful to a stranger
    token = TOKEN.search(ask.text).group(1)  # type: ignore[union-attr]

    for _click in range(2):  # clicking the link twice sends the confirmation once
        response = client.post("/api/email/verify", json={"token": token})
        assert response.get_json() == {"verified": True, "email": SHOPPER_EMAIL, "order_number": number}
    assert mailbox.subjects() == [ask.subject, f"Your order {number} is confirmed"]


def test_card_order_is_confirmed_once_when_paid(client: FlaskClient, db_session: Session, tee: ProductVariant,
                                                fake_stripe: FakeStripe, mailbox: RecordingSender) -> None:
    verify_address(db_session, SHOPPER_EMAIL)
    number = start_checkout(client, [{"variant_id": tee.id, "quantity": 1}], email=SHOPPER_EMAIL)["order_number"]
    assert mailbox.sent == []  # checkout started, not paid: nothing to confirm yet

    order = get_order(db_session, number)
    send_stripe_event(client, completed_event(order, "evt_1"))
    send_stripe_event(client, completed_event(order, "evt_1"))  # Stripe retries the same event
    send_stripe_event(client, completed_event(order, "evt_2"))  # or sends a second one
    assert mailbox.subjects() == [f"Your order {number} is confirmed"]


def test_demo_orders_at_example_com_are_recorded_but_never_sent(client: FlaskClient, db_session: Session,
                                                                 tee: ProductVariant, mailbox: RecordingSender) -> None:
    place_cod(client, [{"variant_id": tee.id, "quantity": 1}], email="buyer@example.com")
    [row] = outbox_rows(db_session)
    assert (row.kind, row.status, row.suppressed_reason) == ("order_confirmation", EmailStatus.SUPPRESSED, "blocked_domain")
    assert mailbox.sent == []


# --- status changes ----------------------------------------------------------------------------------


def test_shipping_journey_sends_one_email_per_step(admin_client: FlaskClient, db_session: Session,
                                                    seeded: SeedCounts, mailbox: RecordingSender) -> None:
    sendable_order(db_session, "KO-1003")  # processing
    url = "/api/admin/orders/KO-1003/status"
    admin_post(admin_client, url, {"status": "shipped", "carrier": "UPS", "tracking_number": "1Z999",
                                   "estimated_delivery": "2026-10-23"})
    admin_post(admin_client, url, {"status": "delayed", "note": "Storm at the depot."})
    admin_post(admin_client, url, {"status": "out_for_delivery"})
    admin_post(admin_client, url, {"status": "delivered"})

    assert mailbox.subjects() == [
        "Your order KO-1003 is on its way",
        "Your order KO-1003 is delayed",
        "Your order KO-1003 is out for delivery",
        "Your order KO-1003 was delivered",
    ]
    dispatched, delayed = mailbox.sent[0], mailbox.sent[1]
    assert "UPS" in dispatched.text and "1Z999" in dispatched.text and "Friday, October 23" in dispatched.text
    assert "Storm at the depot." in delayed.text


def test_every_delay_is_its_own_email(admin_client: FlaskClient, db_session: Session,
                                      seeded: SeedCounts, mailbox: RecordingSender) -> None:
    sendable_order(db_session, "KO-1003")
    url = "/api/admin/orders/KO-1003/status"
    admin_post(admin_client, url, {"status": "shipped", "carrier": "UPS", "tracking_number": "1Z999"})
    for note in ("Storm.", "Still a storm."):
        admin_post(admin_client, url, {"status": "delayed", "note": note})
        admin_post(admin_client, url, {"status": "shipped"})
    assert mailbox.subjects().count("Your order KO-1003 is delayed") == 2  # keyed by event, not by status


def test_unverified_address_gets_no_status_emails(admin_client: FlaskClient, db_session: Session,
                                                  seeded: SeedCounts, mailbox: RecordingSender) -> None:
    sendable_order(db_session, "KO-1003", verified=False)
    admin_post(admin_client, "/api/admin/orders/KO-1003/status",
               {"status": "shipped", "carrier": "UPS", "tracking_number": "1Z999"})
    [row] = outbox_rows(db_session)
    assert (row.status, row.suppressed_reason) == (EmailStatus.SUPPRESSED, "unverified")
    assert mailbox.sent == []


# --- cancellations, returns and refunds (the admin approval flow) ------------------------------------------


def test_cancelling_a_paid_order_emails_the_refund(admin_client: FlaskClient, db_session: Session, seeded: SeedCounts,
                                                    mailbox: RecordingSender, no_refunds: None) -> None:
    order = sendable_order(db_session, "KO-1003")
    order.stripe_payment_intent = "pi_sandbox_1003"
    db_session.commit()
    admin_post(admin_client, "/api/admin/orders/KO-1003/status", {"status": "cancelled", "note": "Out of stock."})

    [email] = mailbox.sent
    assert email.subject == "Your order KO-1003 has been cancelled"
    assert f"We've refunded {notifications.money(order.total_cents)} to your original payment method." in email.text
    assert "Out of stock." in email.text


def test_cancelling_a_cod_order_says_nothing_was_charged(client: FlaskClient, admin_client: FlaskClient,
                                                         db_session: Session, tee: ProductVariant,
                                                         mailbox: RecordingSender) -> None:
    verify_address(db_session, SHOPPER_EMAIL)
    number = place_cod(client, [{"variant_id": tee.id, "quantity": 1}], email=SHOPPER_EMAIL)["order_number"]
    admin_post(admin_client, f"/api/admin/orders/{number}/status", {"status": "cancelled"})
    assert "nothing to refund" in mailbox.sent[-1].text


def test_cancelling_an_unpaid_checkout_sends_nothing(admin_client: FlaskClient, db_session: Session,
                                                     seeded: SeedCounts, mailbox: RecordingSender) -> None:
    order = sendable_order(db_session, "KO-1003")
    order.status = OrderStatus.PENDING_PAYMENT
    db_session.commit()
    admin_post(admin_client, "/api/admin/orders/KO-1003/status", {"status": "cancelled"})
    assert outbox_rows(db_session) == []


def start_return(client: FlaskClient, number: str) -> int:
    order_item_id = client.post("/api/returns/eligibility", json={"order_number": number, "email": SHOPPER_EMAIL}
                                ).get_json()["items"][0]["order_item_id"]
    response = client.post("/api/returns", json={
        "order_number": number, "email": SHOPPER_EMAIL, "type": "refund", "reason": "doesnt_fit",
        "items": [{"order_item_id": order_item_id, "quantity": 1}], "condition_confirmed": True})
    assert response.status_code == 201, response.get_json()
    return int(response.get_json()["id"])


def test_return_approved_then_refunded(client: FlaskClient, admin_client: FlaskClient, db_session: Session,
                                       seeded: SeedCounts, mailbox: RecordingSender, no_refunds: None,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
    from app import returns

    monkeypatch.setattr(returns, "utc_now", lambda: FIXED_NOW)
    sendable_order(db_session, "KO-1005")  # delivered, inside the return window
    return_id = start_return(client, "KO-1005")
    assert mailbox.sent == []  # the customer's own request sends nothing (not in the plan's table)

    url = f"/api/admin/returns/{return_id}/status"
    for status in ("approved", "label_sent", "received", "refunded"):
        admin_post(admin_client, url, {"status": status})

    assert mailbox.subjects() == ["Your return for order KO-1005 is approved", "Your refund for order KO-1005"]
    approved, refunded = mailbox.sent
    assert "prepaid return label" in approved.text  # a US order: free label
    assert "Merino Crew Sweater" in approved.text
    assert "$89.00" in refunded.text and "To your original payment method" in refunded.text


def test_rejected_return_explains_why(client: FlaskClient, admin_client: FlaskClient, db_session: Session,
                                      seeded: SeedCounts, mailbox: RecordingSender, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import returns

    monkeypatch.setattr(returns, "utc_now", lambda: FIXED_NOW)
    sendable_order(db_session, "KO-1005")
    return_id = start_return(client, "KO-1005")
    admin_post(admin_client, f"/api/admin/returns/{return_id}/status",
               {"status": "rejected", "note": "The tags were removed."})
    [email] = mailbox.sent
    assert email.subject == "About your return for order KO-1005"
    assert "The tags were removed." in email.text


# --- tickets ---------------------------------------------------------------------------------------------


def test_new_ticket_alerts_the_store_owner(client: FlaskClient, db_session: Session, seeded: SeedCounts,
                                           mailbox: RecordingSender) -> None:
    response = client.post("/api/support/contact", json={
        "name": "Ayesha", "email": "ayesha@example.com", "subject": "Wrong size",
        "message": "I got an L instead of an M, can you help?"})
    assert response.status_code == 201

    [alert] = mailbox.sent
    assert alert.to == "owner@kora.local"  # our own inbox: no verification needed
    assert alert.subject == f"New support ticket #{response.get_json()['id']}: Wrong size"
    assert alert.reply_to == "ayesha@example.com"  # "Reply" answers the customer
    assert "I got an L instead of an M" in alert.text
