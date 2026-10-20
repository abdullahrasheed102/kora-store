"""Cash on delivery, payment status on every order, the payment-status migration, and `flask policies sync`."""

from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from flask_migrate import downgrade, upgrade
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Order, OrderStatus, PaymentMethod, PaymentStatus, Policy, ProductVariant
from app.policies import load_policy_seed, sync_policies
from app.seed import SeedCounts
from tests.conftest import FakeStripe, csrf_headers, send_stripe_event
from tests.test_checkout import ADDRESS, checkout_body, completed_event, get_order, variant

PHONE = "+1 (512) 555-0147"
PAYMENT_MIGRATION = "6c80859c1e35"
BEFORE_PAYMENT_MIGRATION = "3cce4c73efd7"


def cod_body(items: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    return checkout_body(items, **{"phone": PHONE, **overrides})


def place_cod(client: FlaskClient, items: list[dict[str, Any]], status: int = 201, **overrides: Any) -> Any:
    response = client.post("/api/checkout/cod", json=cod_body(items, **overrides))
    assert response.status_code == status, response.get_json()
    return response.get_json()


def call(client: FlaskClient, method: str, path: str, body: Any = None) -> Any:
    return client.open(path, method=method, json=body, headers=csrf_headers(client))


def set_status(admin: FlaskClient, number: str, status: str, **extra: Any) -> Any:
    return call(admin, "POST", f"/api/admin/orders/{number}/status", {"status": status, **extra})


@pytest.fixture
def tee(db_session: Session, seeded: SeedCounts) -> ProductVariant:
    return variant(db_session, "KO-001-WHIT-M")  # $24, stock 25


# --- placing a COD order -------------------------------------------------------------------------


def test_cod_order_is_confirmed_at_once_and_takes_stock(
    client: FlaskClient, db_session: Session, tee: ProductVariant
) -> None:
    body = place_cod(client, [{"variant_id": tee.id, "quantity": 2}])

    order = get_order(db_session, body["order_number"])
    assert order.status is OrderStatus.PROCESSING  # no payment to wait for
    assert (order.payment_method, order.payment_status) == (PaymentMethod.COD, PaymentStatus.UNPAID)
    assert order.phone == PHONE
    assert order.total_cents == 2 * 2400 + 695  # priced by the server, as for card
    assert variant(db_session, "KO-001-WHIT-M").stock == 23  # reserved at placement
    assert [event.note for event in order.events] == ["Order placed. Payment: cash on delivery."]

    # Straight to our own thank-you page, with a secret token instead of a payment page.
    assert body["checkout_url"].startswith(f"http://localhost:3000/order/success?order={order.order_number}&session_id=cod_")
    token = body["checkout_url"].split("session_id=")[1]
    confirmation = client.get(f"/api/orders/{order.order_number}/confirmation?session_id={token}").get_json()
    assert (confirmation["payment_method"], confirmation["payment_status"]) == ("cod", "unpaid")


def test_cod_needs_a_valid_phone_number(client: FlaskClient, db_session: Session, tee: ProductVariant) -> None:
    line = [{"variant_id": tee.id, "quantity": 1}]
    for i, phone in enumerate((None, "", "12345", "call me maybe", "+1 555 0100 0100 0100 9")):
        # One IP per attempt: refused requests still count toward the COD rate limit (on purpose,
        # so probing isn't free), and this test is about validation, not the limit.
        response = client.post(
            "/api/checkout/cod", json=cod_body(line, phone=phone), environ_base={"REMOTE_ADDR": f"198.51.100.{i}"}
        )
        assert response.status_code == 400, phone
    assert db_session.scalar(select(Order).where(Order.payment_method == PaymentMethod.COD)) is None


def test_cod_is_for_us_addresses_only(client: FlaskClient, tee: ProductVariant) -> None:
    uk = {**ADDRESS, "state": None, "postal_code": "SW1A 1AA", "country": "GB"}
    response = client.post(
        "/api/checkout/cod", json=cod_body([{"variant_id": tee.id, "quantity": 1}], address=uk, shipping_method="international")
    )
    assert response.status_code == 400
    assert "only available for US addresses" in response.get_json()["error"]["message"]


def test_cod_refuses_more_than_is_in_stock_and_saves_nothing(
    client: FlaskClient, db_session: Session, tee: ProductVariant
) -> None:
    tee.stock = 1
    db_session.commit()
    response = client.post("/api/checkout/cod", json=cod_body([{"variant_id": tee.id, "quantity": 2}]))
    assert response.status_code == 409
    assert variant(db_session, "KO-001-WHIT-M").stock == 1
    assert db_session.scalar(select(Order).where(Order.payment_method == PaymentMethod.COD)) is None


def test_admins_cannot_place_cod_orders(admin_client: FlaskClient, tee: ProductVariant) -> None:
    response = call(admin_client, "POST", "/api/checkout/cod", cod_body([{"variant_id": tee.id, "quantity": 1}]))
    assert response.status_code == 403


def test_cod_is_rate_limited_per_ip(client: FlaskClient, tee: ProductVariant) -> None:
    line = [{"variant_id": tee.id, "quantity": 1}]
    statuses = [
        client.post("/api/checkout/cod", json=cod_body(line, phone=f"512555010{i}")).status_code for i in range(4)
    ]
    assert statuses == [201, 201, 201, 429]


def test_cod_is_rate_limited_per_phone_across_ips(client: FlaskClient, tee: ProductVariant) -> None:
    line = [{"variant_id": tee.id, "quantity": 1}]
    statuses = [
        client.post(
            "/api/checkout/cod", json=cod_body(line), environ_base={"REMOTE_ADDR": f"203.0.113.{i}"}
        ).status_code
        for i in range(4)
    ]
    assert statuses == [201, 201, 201, 429]  # same phone, four different IPs


def test_the_sandbox_never_serves_a_cod_order(client: FlaskClient, tee: ProductVariant) -> None:
    token = place_cod(client, [{"variant_id": tee.id, "quantity": 1}])["checkout_url"].split("session_id=")[1]
    assert client.get(f"/api/sandbox/sessions/{token}").status_code == 404


# --- after the order: cash, cancellation, returns ------------------------------------------------


def test_cash_can_only_be_collected_at_delivery(
    client: FlaskClient, admin_client: FlaskClient, db_session: Session, tee: ProductVariant
) -> None:
    number = place_cod(client, [{"variant_id": tee.id, "quantity": 1}])["order_number"]
    collect = f"/api/admin/orders/{number}/cash-collected"

    early = call(admin_client, "POST", collect)
    assert (early.status_code, early.get_json()["error"]["code"]) == (409, "not_delivered_yet")
    assert call(admin_client, "GET", f"/api/admin/orders/{number}").get_json()["can_mark_cash_collected"] is False

    set_status(admin_client, number, "shipped", carrier="UPS", tracking_number="1Z999")
    set_status(admin_client, number, "delivered")
    detail = call(admin_client, "GET", f"/api/admin/orders/{number}").get_json()
    assert (detail["can_mark_cash_collected"], detail["phone"]) == (True, PHONE)

    paid = call(admin_client, "POST", collect)
    assert paid.status_code == 200
    assert paid.get_json()["payment_status"] == "paid"
    assert paid.get_json()["events"][-1]["note"] == "Cash collected on delivery: 30.95 USD."
    assert paid.get_json()["events"][-1]["created_by"] == "admin"

    again = call(admin_client, "POST", collect)
    assert (again.status_code, again.get_json()["error"]["code"]) == (409, "already_paid")


def test_cancelling_a_cod_order_restores_stock_without_a_refund(
    client: FlaskClient, admin_client: FlaskClient, db_session: Session, tee: ProductVariant
) -> None:
    number = place_cod(client, [{"variant_id": tee.id, "quantity": 3}])["order_number"]
    assert variant(db_session, "KO-001-WHIT-M").stock == 22

    response = set_status(admin_client, number, "cancelled", note="Customer changed their mind.")
    assert response.status_code == 200
    order = get_order(db_session, number)
    assert order.status is OrderStatus.CANCELLED
    assert order.payment_status is PaymentStatus.UNPAID  # no cash ever changed hands
    assert variant(db_session, "KO-001-WHIT-M").stock == 25


def test_card_orders_record_paid_and_refunded(
    client: FlaskClient, admin_client: FlaskClient, db_session: Session, fake_stripe: FakeStripe, tee: ProductVariant
) -> None:
    number = client.post("/api/checkout/session", json=checkout_body([{"variant_id": tee.id, "quantity": 1}])).get_json()[
        "order_number"
    ]
    assert get_order(db_session, number).payment_status is PaymentStatus.UNPAID

    send_stripe_event(client, completed_event(get_order(db_session, number)))
    order = get_order(db_session, number)
    assert (order.payment_method, order.payment_status) == (PaymentMethod.CARD, PaymentStatus.PAID)

    set_status(admin_client, number, "cancelled")
    assert fake_stripe.refunds == [f"pi_{number}"]
    assert get_order(db_session, number).payment_status is PaymentStatus.REFUNDED


def test_cod_return_refunds_need_the_cash_first_and_go_by_bank_transfer(
    client: FlaskClient, admin_client: FlaskClient, db_session: Session, fake_stripe: FakeStripe, tee: ProductVariant
) -> None:
    fake_stripe_refunds_before = list(fake_stripe.refunds)
    number = place_cod(client, [{"variant_id": tee.id, "quantity": 1}])["order_number"]
    set_status(admin_client, number, "shipped", carrier="UPS", tracking_number="1Z999")
    set_status(admin_client, number, "delivered")
    order = get_order(db_session, number)
    request = client.post(
        "/api/returns",
        json={"order_number": number, "email": "buyer@example.com", "type": "refund", "reason": "doesnt_fit",
              "condition_confirmed": True, "items": [{"order_item_id": order.items[0].id, "quantity": 1}]},
    )
    assert request.status_code == 201, request.get_json()
    return_id = request.get_json()["id"]
    advance = lambda status: call(admin_client, "POST", f"/api/admin/returns/{return_id}/status", {"status": status})  # noqa: E731
    advance("approved")
    advance("label_sent")
    advance("received")

    blocked = advance("refunded")
    assert (blocked.status_code, blocked.get_json()["error"]["code"]) == (409, "cash_not_collected")

    collected = call(admin_client, "POST", f"/api/admin/orders/{number}/cash-collected")
    assert collected.status_code == 200, collected.get_json()
    refunded = advance("refunded")
    assert refunded.status_code == 200, refunded.get_json()
    order = get_order(db_session, number)
    assert (order.status, order.payment_status) == (OrderStatus.RETURNED, PaymentStatus.REFUNDED)
    assert order.status_note == "Returned; refund issued by bank transfer or store credit."
    assert fake_stripe.refunds == fake_stripe_refunds_before  # no card to refund


# --- showing the payment method -----------------------------------------------------------------


def test_tracking_shows_how_a_cod_order_is_paid(client: FlaskClient, tee: ProductVariant) -> None:
    number = place_cod(client, [{"variant_id": tee.id, "quantity": 1}])["order_number"]
    tracked = client.post("/api/orders/track", json={"order_number": number, "email": "buyer@example.com"}).get_json()
    assert (tracked["payment_method"], tracked["payment_status"], tracked["total_cents"]) == ("cod", "unpaid", 3095)
    assert "phone" not in tracked  # never on the public tracking page

    card = client.post(
        "/api/orders/track", json={"order_number": "KO-1002", "email": "daniel.brooks@example.com"}
    ).get_json()
    assert (card["payment_method"], card["payment_status"], card["total_cents"]) == ("card", "paid", None)


def test_admin_order_list_shows_payment(client: FlaskClient, admin_client: FlaskClient, tee: ProductVariant) -> None:
    number = place_cod(client, [{"variant_id": tee.id, "quantity": 1}])["order_number"]
    rows = call(admin_client, "GET", "/api/admin/orders").get_json()["items"]
    row = next(item for item in rows if item["order_number"] == number)
    assert (row["payment_method"], row["payment_status"]) == ("cod", "unpaid")


def test_seeded_orders_get_a_truthful_payment_status(db_session: Session, seeded: SeedCounts) -> None:
    statuses = {o.order_number: (o.status, o.payment_status) for o in db_session.scalars(select(Order))}
    assert statuses["KO-1001"] == (OrderStatus.DELIVERED, PaymentStatus.PAID)
    assert statuses["KO-1010"] == (OrderStatus.RETURNED, PaymentStatus.REFUNDED)
    assert statuses["KO-1012"][0] is OrderStatus.CANCELLED
    assert all(o.payment_method is PaymentMethod.CARD for o in db_session.scalars(select(Order)))


# --- the migration for orders that existed before payment_status ------------------------------------


def test_migration_marks_existing_orders_by_what_happened_to_them(app: Flask, db_session: Session) -> None:
    downgrade(revision=BEFORE_PAYMENT_MIGRATION)
    try:
        def insert(number: str, status: str, events: list[str], payment_intent: str | None = None) -> None:
            db_session.execute(
                text(
                    "INSERT INTO orders (order_number, email, customer_name, status, subtotal_cents, shipping_cents,"
                    " total_cents, shipping_method, shipping_line1, shipping_city, shipping_postal_code, shipping_country,"
                    " stripe_payment_intent) VALUES (:n, 'a@example.com', 'A', :s, 100, 0, 100, 'standard', '1 St',"
                    " 'Austin', '78701', 'US', :pi)"
                ),
                {"n": number, "s": status, "pi": payment_intent},
            )
            for event in events:
                db_session.execute(
                    text("INSERT INTO order_events (order_id, status) SELECT id, :e FROM orders WHERE order_number = :n"),
                    {"e": event, "n": number},
                )

        insert("KO-1", "delivered", ["processing", "shipped", "delivered"])
        insert("KO-2", "pending_payment", ["pending_payment"])
        insert("KO-3", "cancelled", ["pending_payment", "cancelled"])  # checkout expired: never paid
        insert("KO-4", "cancelled", ["processing", "cancelled"])  # paid, then cancelled by staff
        insert("KO-5", "cancelled", ["pending_payment", "cancelled"], payment_intent="pi_late")  # paid too late, refunded
        insert("KO-6", "returned", ["processing", "delivered", "returned"])
        db_session.commit()

        upgrade(revision=PAYMENT_MIGRATION)

        rows = dict(db_session.execute(text("SELECT order_number, payment_method || '/' || payment_status FROM orders")).all())
        assert rows == {
            "KO-1": "card/paid",
            "KO-2": "card/unpaid",
            "KO-3": "card/unpaid",
            "KO-4": "card/refunded",
            "KO-5": "card/refunded",
            "KO-6": "card/refunded",
        }
    finally:
        db_session.rollback()
        upgrade()  # always leave the test database at the latest migration


# --- flask policies sync -----------------------------------------------------------------------------


def policy(session: Session, key: str) -> Policy:
    session.expire_all()
    return session.scalars(select(Policy).where(Policy.key == key)).one()


def test_policy_sync_updates_only_higher_versions_and_is_idempotent(db_session: Session, seeded: SeedCounts) -> None:
    rows = load_policy_seed()
    shipping = policy(db_session, "shipping")
    shipping.body, shipping.seed_version = "Old shipping text.", 1  # as production was before COD
    db_session.commit()

    first = sync_policies(db_session, rows)
    assert first.updated == ["shipping"]
    assert "cash on delivery" in policy(db_session, "shipping").body
    assert policy(db_session, "shipping").seed_version == 2

    second = sync_policies(db_session, rows)
    assert (second.added, second.updated) == ([], [])  # nothing left to do


def test_policy_sync_keeps_admin_edits_of_the_current_version(
    admin_client: FlaskClient, db_session: Session, seeded: SeedCounts
) -> None:
    edit = {"title": "Refunds", "summary": None, "body": "Our own refund wording, edited by an admin."}
    assert call(admin_client, "PUT", "/api/admin/policies/refunds", edit).status_code == 200

    sync_policies(db_session, load_policy_seed())
    assert policy(db_session, "refunds").body == edit["body"]  # same version: the admin's text wins


def test_policy_sync_adds_a_missing_policy_and_never_deletes(db_session: Session, seeded: SeedCounts) -> None:
    db_session.delete(policy(db_session, "cancellations"))
    db_session.commit()
    report = sync_policies(db_session, [row for row in load_policy_seed() if row["key"] == "cancellations"])
    assert report.added == ["cancellations"]
    assert db_session.scalar(select(text("count(*)")).select_from(Policy)) == 5  # the other four untouched


def test_policies_cli(app: Flask, db_session: Session, seeded: SeedCounts) -> None:
    result = app.test_cli_runner().invoke(args=["policies", "sync"])
    assert result.exit_code == 0, result.output
    assert result.output.startswith("Policies: 0 added, 0 updated, 5 unchanged.")


def test_cod_policy_text_is_in_the_seed() -> None:
    rows = {row["key"]: row for row in load_policy_seed()}
    assert "cash on delivery" in rows["shipping"]["body"]
    assert "bank transfer or store credit" in rows["refunds"]["body"]
