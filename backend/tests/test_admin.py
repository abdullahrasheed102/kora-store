"""Admin: permissions on every route, products and stock, the order state machine, returns,
tickets, policies and stats."""

import re
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import admin as admin_service
from app.models import (
    EventActor,
    Order,
    OrderStatus,
    Product,
    ProductVariant,
    SupportTicket,
    User,
    UserRole,
)
from app.payments import SandboxProvider
from app.seed import SeedCounts
from tests.conftest import FIXED_NOW, csrf_headers


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_service, "utc_now", lambda: FIXED_NOW)
    from app import returns

    monkeypatch.setattr(returns, "utc_now", lambda: FIXED_NOW)


@pytest.fixture
def refunds(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int | None]]:
    """Records sandbox refunds (payment id, amount; None = full)."""
    calls: list[tuple[str, int | None]] = []
    monkeypatch.setattr(SandboxProvider, "refund_payment",
                        lambda _self, payment_id, idempotency_key, amount_cents=None: calls.append((payment_id, amount_cents)))
    return calls


def call(client: FlaskClient, method: str, path: str, body: Any = None) -> Any:
    kwargs: dict[str, Any] = {"headers": csrf_headers(client)}
    if body is not None:
        kwargs["json"] = body
    return client.open(path, method=method, **kwargs)


def order(session: Session, number: str) -> Order:
    session.expire_all()
    return session.scalars(select(Order).where(Order.order_number == number)).one()


def variant(session: Session, sku: str) -> ProductVariant:
    session.expire_all()
    return session.scalars(select(ProductVariant).where(ProductVariant.sku == sku)).one()


# --- permissions: discovered automatically, so new routes are covered too -------------------------


def admin_routes(app: Flask) -> list[tuple[str, str]]:
    routes = []
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith("/api/admin"):
            path = re.sub(r"<int:\w+>", "1", rule.rule)
            path = re.sub(r"<\w+>", "x", path)
            routes += [(method, path) for method in sorted(rule.methods - {"HEAD", "OPTIONS"})]
    return routes


def test_there_are_admin_routes_to_check(app: Flask) -> None:
    assert len(admin_routes(app)) >= 15  # guards against the discovery silently finding nothing


def test_every_admin_route_needs_a_login(app: Flask, client: FlaskClient, seeded: SeedCounts) -> None:
    for method, path in admin_routes(app):
        response = client.open(path, method=method, json={})
        assert response.status_code == 401, (method, path, response.status_code)


def test_every_admin_route_refuses_customers(app: Flask, logged_in: FlaskClient, seeded: SeedCounts) -> None:
    for method, path in admin_routes(app):
        response = call(logged_in, method, path, {})  # WITH a valid CSRF header: only the role is missing
        assert response.status_code == 403, (method, path, response.status_code)
        assert response.get_json()["error"]["code"] == "forbidden", (method, path)


def test_every_admin_route_lets_admins_through(app: Flask, admin_client: FlaskClient, seeded: SeedCounts) -> None:
    for method, path in admin_routes(app):
        response = call(admin_client, method, path, {})
        # 404/400/409 are fine (dummy ids and bodies); what matters is it wasn't 401/403.
        assert response.status_code not in (401, 403), (method, path, response.status_code)


def test_admin_writes_still_need_csrf(admin_client: FlaskClient, seeded: SeedCounts) -> None:
    response = admin_client.patch("/api/admin/products/1", json={"name": "Hacked"})
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "csrf_failed"


def test_removing_the_admin_role_takes_effect_immediately(
    admin_client: FlaskClient, admin_user: User, db_session: Session, seeded: SeedCounts
) -> None:
    assert admin_client.get("/api/admin/stats").status_code == 200
    admin_user.role = UserRole.CUSTOMER
    db_session.commit()
    # Same cookie, same token: the role is read from the database on every request.
    assert admin_client.get("/api/admin/stats").status_code == 403


# --- products and stock ------------------------------------------------------------------------------

NEW_PRODUCT = {
    "slug": "linen-trousers",
    "name": "Linen Trousers",
    "category": "Bottoms",
    "description": "Wide-leg linen trousers.",
    "price_cents": 6800,
}


def test_create_and_edit_a_product(admin_client: FlaskClient, client: FlaskClient, seeded: SeedCounts) -> None:
    created = call(admin_client, "POST", "/api/admin/products", NEW_PRODUCT)
    assert created.status_code == 201
    product_id = created.get_json()["id"]

    variant_response = call(admin_client, "POST", f"/api/admin/products/{product_id}/variants",
                            {"sku": "KO-021-NATU-M", "size": "M", "color": "Natural", "stock": 8})
    assert variant_response.status_code == 201
    assert client.get("/api/products/linen-trousers").get_json()["variants"][0]["stock"] == 8

    edited = call(admin_client, "PATCH", f"/api/admin/products/{product_id}", {"price_cents": 6200})
    body = edited.get_json()
    assert body["price_cents"] == 6200
    assert body["name"] == "Linen Trousers"  # PATCH: fields not sent are left alone


def test_deactivated_products_leave_the_shop(admin_client: FlaskClient, client: FlaskClient, db_session: Session,
                                             seeded: SeedCounts) -> None:
    tee = db_session.scalars(select(Product).where(Product.slug == "everyday-cotton-tee")).one()
    call(admin_client, "PATCH", f"/api/admin/products/{tee.id}", {"is_active": False})
    assert client.get("/api/products/everyday-cotton-tee").status_code == 404
    assert call(admin_client, "GET", f"/api/admin/products/{tee.id}").status_code == 200  # admins still see it


@pytest.mark.parametrize(
    ("body", "status"),
    [
        (NEW_PRODUCT | {"slug": "everyday-cotton-tee"}, 409),  # slug taken
        (NEW_PRODUCT | {"slug": "Bad Slug!"}, 400),
        (NEW_PRODUCT | {"price_cents": -1}, 400),
        (NEW_PRODUCT | {"image_url": "javascript:alert(1)"}, 400),  # only http(s) image URLs
    ],
)
def test_product_validation(admin_client: FlaskClient, seeded: SeedCounts, body: dict[str, Any], status: int) -> None:
    assert call(admin_client, "POST", "/api/admin/products", body).status_code == status


def test_stock_changes_are_deltas_so_concurrent_sales_are_kept(
    admin_client: FlaskClient, db_session: Session, seeded: SeedCounts
) -> None:
    tee = variant(db_session, "KO-001-WHIT-M")  # 25 in stock; the admin's screen says 25
    tee.stock -= 1  # a customer buys one while the admin is typing
    db_session.commit()

    response = call(admin_client, "PATCH", f"/api/admin/variants/{tee.id}", {"stock_change": 10})
    assert response.status_code == 200
    # 24 + 10. Had the admin typed "35" as an absolute value, the sale would have been erased.
    assert variant(db_session, "KO-001-WHIT-M").stock == 34


def test_stock_cannot_go_negative(admin_client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    tee = variant(db_session, "KO-001-WHIT-M")
    response = call(admin_client, "PATCH", f"/api/admin/variants/{tee.id}", {"stock_change": -26})
    assert response.status_code == 409
    assert variant(db_session, "KO-001-WHIT-M").stock == 25


def test_duplicate_variant_is_refused(admin_client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    tee = variant(db_session, "KO-001-WHIT-M")
    response = call(admin_client, "POST", f"/api/admin/products/{tee.product_id}/variants",
                    {"sku": "KO-001-WHIT-M2", "size": "M", "color": "White"})
    assert response.status_code == 409


# --- orders: the state machine ------------------------------------------------------------------------


def test_order_list_filters_and_searches(admin_client: FlaskClient, seeded: SeedCounts) -> None:
    processing = call(admin_client, "GET", "/api/admin/orders?status=processing").get_json()
    assert {o["order_number"] for o in processing["items"]} == {"KO-1003", "KO-1008"}
    search = call(admin_client, "GET", "/api/admin/orders?q=olivia").get_json()
    assert [o["order_number"] for o in search["items"]] == ["KO-1005"]


def test_order_detail_lists_allowed_next_statuses(admin_client: FlaskClient, seeded: SeedCounts) -> None:
    body = call(admin_client, "GET", "/api/admin/orders/KO-1003").get_json()
    assert body["allowed_next_statuses"] == ["cancelled", "partially_shipped", "shipped"]
    assert body["shipping_address"]["line1"] == "123 Demo Street"  # admins see the full address


def test_shipping_needs_tracking_and_writes_an_admin_event(admin_client: FlaskClient, db_session: Session,
                                                          seeded: SeedCounts) -> None:
    path = "/api/admin/orders/KO-1003/status"
    assert call(admin_client, "POST", path, {"status": "shipped"}).status_code == 400

    response = call(admin_client, "POST", path, {"status": "shipped", "carrier": "UPS", "tracking_number": "1Z999"})
    assert response.status_code == 200
    o = order(db_session, "KO-1003")
    assert (o.status, o.carrier, o.tracking_number) == (OrderStatus.SHIPPED, "UPS", "1Z999")
    assert o.events[-1].created_by is EventActor.ADMIN  # the audit trail
    assert response.get_json()["allowed_next_statuses"] == ["delayed", "delivered", "out_for_delivery"]


@pytest.mark.parametrize(
    ("number", "target"),
    [("KO-1001", "processing"), ("KO-1001", "shipped"), ("KO-1012", "processing"), ("KO-1005", "returned"),
     ("KO-1002", "cancelled")],
)
def test_impossible_transitions_are_refused(admin_client: FlaskClient, seeded: SeedCounts, number: str, target: str) -> None:
    response = call(admin_client, "POST", f"/api/admin/orders/{number}/status", {"status": target})
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "invalid_transition"


def test_delay_needs_a_note_for_the_customer(admin_client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    path = "/api/admin/orders/KO-1002/status"
    assert call(admin_client, "POST", path, {"status": "delayed"}).status_code == 400
    assert call(admin_client, "POST", path, {"status": "delayed", "note": "Snow storm in Denver."}).status_code == 200
    assert order(db_session, "KO-1002").status_note == "Snow storm in Denver."


def test_delivered_starts_the_return_window(admin_client: FlaskClient, client: FlaskClient, db_session: Session,
                                            seeded: SeedCounts) -> None:
    call(admin_client, "POST", "/api/admin/orders/KO-1004/status", {"status": "delivered"})
    o = order(db_session, "KO-1004")
    assert o.delivered_at == FIXED_NOW
    eligibility = client.post("/api/returns/eligibility", json={"order_number": "KO-1004", "email": o.email}).get_json()
    assert eligibility["eligible"] is True and eligibility["days_left"] == 30


def test_cancelling_a_paid_order_restocks_and_refunds(admin_client: FlaskClient, db_session: Session,
                                                       seeded: SeedCounts, refunds: list[Any]) -> None:
    o = order(db_session, "KO-1003")  # processing: linen shirt S/Sand + tote
    o.stripe_payment_intent = "pi_sandbox_1003"
    db_session.commit()
    shirt_before = variant(db_session, "KO-002-SAND-S").stock

    response = call(admin_client, "POST", "/api/admin/orders/KO-1003/status", {"status": "cancelled", "note": "Customer asked."})
    assert response.status_code == 200
    assert variant(db_session, "KO-002-SAND-S").stock == shirt_before + 1
    assert refunds == [("pi_sandbox_1003", None)]  # full refund


def test_cancelling_an_unpaid_order_takes_no_stock_back(admin_client: FlaskClient, db_session: Session,
                                                         seeded: SeedCounts, refunds: list[Any]) -> None:
    o = order(db_session, "KO-1003")
    o.status = OrderStatus.PENDING_PAYMENT  # stock was never taken for an unpaid order
    db_session.commit()
    before = variant(db_session, "KO-002-SAND-S").stock
    call(admin_client, "POST", "/api/admin/orders/KO-1003/status", {"status": "cancelled"})
    assert variant(db_session, "KO-002-SAND-S").stock == before
    assert refunds == []


# --- returns -----------------------------------------------------------------------------------------


def start_return(client: FlaskClient, session: Session, number: str, item_index: int = 0, quantity: int = 1,
                 **extra: Any) -> int:
    o = order(session, number)
    body = {"order_number": number, "email": o.email, "type": "refund", "reason": "doesnt_fit",
            "items": [{"order_item_id": o.items[item_index].id, "quantity": quantity}], "condition_confirmed": True}
    response = client.post("/api/returns", json=body | extra)
    assert response.status_code == 201, response.get_json()
    return int(response.get_json()["id"])


def move(admin_client: FlaskClient, return_id: int, status: str, note: str | None = None) -> Any:
    return call(admin_client, "POST", f"/api/admin/returns/{return_id}/status", {"status": status, "note": note})


def test_full_return_lifecycle(admin_client: FlaskClient, client: FlaskClient, db_session: Session,
                               seeded: SeedCounts, refunds: list[Any]) -> None:
    o = order(db_session, "KO-1005")
    o.stripe_payment_intent = "pi_sandbox_1005"
    db_session.commit()
    sweater = start_return(client, db_session, "KO-1005", 0)
    beanie = start_return(client, db_session, "KO-1005", 1)
    stock_before = variant(db_session, "KO-003-OATM-S").stock

    for step in ("approved", "label_sent", "received"):
        assert move(admin_client, sweater, step).status_code == 200
    assert variant(db_session, "KO-003-OATM-S").stock == stock_before + 1  # back on the shelf

    assert move(admin_client, sweater, "refunded").status_code == 200
    assert refunds == [("pi_sandbox_1005", 8900)]  # partial: the sweater only
    assert order(db_session, "KO-1005").status is OrderStatus.DELIVERED  # the beanie isn't refunded yet

    for step in ("approved", "received", "refunded"):
        move(admin_client, beanie, step)
    assert refunds[-1] == ("pi_sandbox_1005", 2200)
    o = order(db_session, "KO-1005")
    assert o.status is OrderStatus.RETURNED  # every item refunded → the order is returned
    assert o.events[-1].status is OrderStatus.RETURNED and o.events[-1].created_by is EventActor.ADMIN


def test_return_transitions_are_enforced(admin_client: FlaskClient, client: FlaskClient, db_session: Session,
                                         seeded: SeedCounts) -> None:
    request_id = start_return(client, db_session, "KO-1005")
    assert move(admin_client, request_id, "refunded").status_code == 409  # can't refund before receiving
    assert move(admin_client, request_id, "rejected").status_code == 400  # rejecting needs a reason
    assert move(admin_client, request_id, "rejected", "Worn, tags removed.").status_code == 200
    assert move(admin_client, request_id, "approved").status_code == 409  # rejected is final


def test_exchanges_are_never_refunded(admin_client: FlaskClient, client: FlaskClient, db_session: Session,
                                      seeded: SeedCounts) -> None:
    target = variant(db_session, "KO-003-OATM-M")
    request_id = start_return(client, db_session, "KO-1005", 0, type="exchange", exchange_variant_id=target.id)
    move(admin_client, request_id, "approved")
    move(admin_client, request_id, "received")
    assert move(admin_client, request_id, "refunded").status_code == 409
    listed = call(admin_client, "GET", "/api/admin/returns?status=received").get_json()["items"]
    assert listed[0]["allowed_next_statuses"] == []


# --- tickets and the contact form ----------------------------------------------------------------------


def test_contact_form_creates_a_ticket(admin_client: FlaskClient, client: FlaskClient, db_session: Session,
                                       seeded: SeedCounts) -> None:
    email = order(db_session, "KO-1002").email
    response = client.post("/api/support/contact", json={
        "name": "Daniel", "email": email, "order_number": "1002", "subject": "Where is my jacket?",
        "message": "It was supposed to arrive yesterday.",
    })
    assert response.status_code == 201
    tickets = call(admin_client, "GET", "/api/admin/tickets").get_json()["items"]
    assert tickets[0]["order_number"] == "KO-1002" and tickets[0]["source"] == "contact_form"


def test_contact_form_does_not_link_someone_elses_order(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    client.post("/api/support/contact", json={
        "name": "Mallory", "email": "mallory@example.com", "order_number": "KO-1002", "subject": "Hi",
        "message": "Tell me about this order please.",
    })
    ticket = db_session.scalars(select(SupportTicket)).one()
    assert ticket.order_id is None
    assert "doesn't match their email" in ticket.summary


def test_tickets_are_sorted_and_updatable(admin_client: FlaskClient, client: FlaskClient, db_session: Session,
                                          seeded: SeedCounts) -> None:
    for subject in ("First", "Second"):
        client.post("/api/support/contact", json={"name": "A", "email": "a@example.com", "subject": subject,
                                                  "message": "Some message text."})
    second = db_session.scalars(select(SupportTicket).where(SupportTicket.subject == "Second")).one()
    call(admin_client, "PATCH", f"/api/admin/tickets/{second.id}", {"priority": "urgent", "status": "in_progress"})
    subjects = [t["subject"] for t in call(admin_client, "GET", "/api/admin/tickets").get_json()["items"]]
    assert subjects == ["Second", "First"]  # urgent first


def test_contact_form_is_rate_limited(client: FlaskClient, seeded: SeedCounts) -> None:
    body = {"name": "A", "email": "a@example.com", "subject": "Hi", "message": "Some message text."}
    statuses = [client.post("/api/support/contact", json=body).status_code for _ in range(6)]
    assert statuses == [201] * 5 + [429]


# --- policies and stats --------------------------------------------------------------------------------


def test_policy_edits_show_on_the_site(admin_client: FlaskClient, client: FlaskClient, seeded: SeedCounts) -> None:
    body = {"title": "Shipping", "body": "Free US shipping on orders over $100."}
    assert call(admin_client, "PUT", "/api/admin/policies/shipping", body).status_code == 200
    assert client.get("/api/policies/shipping").get_json()["body"] == body["body"]
    assert call(admin_client, "PUT", "/api/admin/policies/shipping", {"title": " ", "body": "x"}).status_code == 400


def test_stats_match_the_orders(admin_client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    body = call(admin_client, "GET", "/api/admin/stats").get_json()
    paid = [o for o in db_session.scalars(select(Order)) if o.status not in (OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED)]
    last_30 = [o for o in paid if o.created_at >= FIXED_NOW - admin_service.timedelta(days=30)]

    assert body["revenue_30d_cents"] == sum(o.total_cents for o in last_30)
    assert body["orders_30d"] == len(last_30)
    assert sum(day["revenue_cents"] for day in body["daily_revenue"]) == body["revenue_30d_cents"]
    assert len(body["daily_revenue"]) == 30
    assert body["orders_by_status"]["delivered"] == 4
    assert body["orders_to_ship"] == 3  # KO-1003, KO-1008 processing + KO-1006 partially shipped
    # The joggers are sold out, so they lead the low-stock list.
    assert body["low_stock"][0]["stock"] == 0
    assert all(item["stock"] <= body["low_stock_threshold"] for item in body["low_stock"])


def test_admin_responses_are_not_cached(admin_client: FlaskClient, seeded: SeedCounts) -> None:
    assert admin_client.get("/api/admin/stats").headers["Cache-Control"] == "no-store"



# --- the admin experience: role hint in the session, no ordering ------------------------------------


def jwt_claims(client: FlaskClient) -> dict[str, Any]:
    import base64
    import json

    cookie = client.get_cookie("access_token_cookie")
    assert cookie is not None
    payload = cookie.value.split(".")[1]
    return dict(json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))))


def test_login_puts_the_role_hint_in_the_session(admin_client: FlaskClient, logged_in: FlaskClient) -> None:
    assert jwt_claims(admin_client)["role"] == "admin"
    assert jwt_claims(logged_in)["role"] == "customer"


def test_a_forged_role_hint_unlocks_nothing(app: Flask, logged_in: FlaskClient, customer: User, seeded: SeedCounts) -> None:
    from flask_jwt_extended import create_access_token

    # Even a VALIDLY SIGNED token that claims "admin" doesn't help: the role comes from the database.
    with app.app_context():
        token = create_access_token(identity=str(customer.id), additional_claims={"role": "admin"})
    logged_in.set_cookie("access_token_cookie", token)
    assert logged_in.get("/api/admin/stats").status_code == 403


def test_admins_cannot_check_out(admin_client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    tee = variant(db_session, "KO-001-WHIT-M")
    body = {"address": {"name": "Store Admin", "line1": "1 Main St", "city": "Austin", "state": "TX",
                        "postal_code": "78701", "country": "US"},
            "shipping_method": "standard", "items": [{"variant_id": tee.id, "quantity": 1}]}
    response = call(admin_client, "POST", "/api/checkout/session", body)

    assert response.status_code == 403
    assert response.get_json()["error"] == {
        "code": "admin_cannot_order",
        "message": "Admin accounts can't place orders. Log in with a customer account to test checkout.",
    }
    assert db_session.scalars(select(Order).where(Order.status == OrderStatus.PENDING_PAYMENT)).all() == []
