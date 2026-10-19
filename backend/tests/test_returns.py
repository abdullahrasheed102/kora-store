"""Return eligibility: one test per rule in the returns policy, plus the API and the pages' data.

Rules (app/returns.py):
  1 only delivered orders        2 not cancelled          3 not already returned
  4 within 30 days of delivery   5 no final-sale items    6 no more than bought (minus open returns)
  7 condition confirmed          8 US: free label, else customer pays   9 exchange: same product, in stock
"""

from datetime import timedelta
from typing import Any

import pytest
from flask.testing import FlaskClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import returns
from app.errors import APIError
from app.models import (
    Order,
    OrderStatus,
    ProductVariant,
    ReturnCreatedBy,
    ReturnRequest,
    ReturnStatus,
    ReturnType,
    User,
)
from app.returns import CreateReturnBody, check_eligibility, create_return, find_order
from app.seed import SeedCounts
from tests.conftest import FIXED_NOW, csrf_headers

@pytest.fixture(autouse=True)
def frozen_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """The seed dates are relative to FIXED_NOW, so the API must use the same 'now'."""
    monkeypatch.setattr(returns, "utc_now", lambda: FIXED_NOW)


def order(session: Session, number: str) -> Order:
    session.expire_all()
    return session.scalars(select(Order).where(Order.order_number == number)).one()


def eligibility(session: Session, number: str, now: Any = FIXED_NOW) -> returns.Eligibility:
    return check_eligibility(session, order(session, number), now)


def item_named(result: returns.Eligibility, name: str) -> returns.ItemEligibility:
    return next(entry for entry in result.items if entry.item.product_name.startswith(name))


def body_for(o: Order, **overrides: Any) -> CreateReturnBody:
    fields: dict[str, Any] = {
        "order_number": o.order_number,
        "email": o.email,
        "items": [{"order_item_id": o.items[0].id, "quantity": 1}],
        "type": "refund",
        "reason": "doesnt_fit",
        "condition_confirmed": True,
    }
    return CreateReturnBody.model_validate(fields | overrides)


# --- rule 1: delivered only ---------------------------------------------------------------------


def test_rule1_order_must_be_delivered(db_session: Session, seeded: SeedCounts) -> None:
    result = eligibility(db_session, "KO-1002")  # shipped, not delivered
    assert not result.eligible
    assert result.refusal and result.refusal.code == "not_delivered"


# --- rule 2: not cancelled ----------------------------------------------------------------------


def test_rule2_cancelled_order_cannot_be_returned(db_session: Session, seeded: SeedCounts) -> None:
    result = eligibility(db_session, "KO-1012")
    assert result.refusal and result.refusal.code == "order_cancelled"


# --- rule 3: not already returned ---------------------------------------------------------------


def test_rule3_returned_order_cannot_be_returned_again(db_session: Session, seeded: SeedCounts) -> None:
    result = eligibility(db_session, "KO-1010")
    assert result.refusal and result.refusal.code == "already_returned"


# --- rule 4: 30-day window ----------------------------------------------------------------------


def test_rule4_inside_the_window_is_eligible(db_session: Session, seeded: SeedCounts) -> None:
    result = eligibility(db_session, "KO-1005")  # delivered 22 days ago
    assert result.eligible
    assert result.refusal is None
    assert all(entry.returnable_quantity == 1 for entry in result.items)


def test_rule4_outside_the_window_is_refused(db_session: Session, seeded: SeedCounts) -> None:
    result = eligibility(db_session, "KO-1007")  # delivered 49 days ago
    assert not result.eligible
    assert result.refusal and result.refusal.code == "window_closed"
    assert "within 30 days" in result.refusal.message


def test_rule4_day_30_still_counts_and_one_minute_later_does_not(db_session: Session, seeded: SeedCounts) -> None:
    delivered = order(db_session, "KO-1005").delivered_at
    assert delivered is not None
    assert eligibility(db_session, "KO-1005", delivered + timedelta(days=30)).eligible
    assert not eligibility(db_session, "KO-1005", delivered + timedelta(days=30, minutes=1)).eligible


# --- rule 5: final sale -------------------------------------------------------------------------


def test_rule5_final_sale_items_are_refused_others_are_not(db_session: Session, seeded: SeedCounts) -> None:
    result = eligibility(db_session, "KO-1011")  # crew socks (final sale) + leather belt
    socks = item_named(result, "Crew Socks")
    belt = item_named(result, "Leather Belt")
    assert socks.returnable_quantity == 0 and socks.refusal and socks.refusal.code == "final_sale"
    assert belt.returnable_quantity == 1 and belt.refusal is None
    assert result.eligible  # the order as a whole still has something returnable


def test_rule5_uses_the_snapshot_not_todays_product(db_session: Session, seeded: SeedCounts) -> None:
    # If the socks stop being final sale today, the order still says what was true at purchase.
    o = order(db_session, "KO-1011")
    socks = next(item for item in o.items if item.product_name.startswith("Crew Socks"))
    assert socks.variant is not None
    socks.variant.product.is_final_sale = False
    db_session.commit()
    assert item_named(eligibility(db_session, "KO-1011"), "Crew Socks").refusal is not None


# --- rule 6: quantities -------------------------------------------------------------------------


def test_rule6_cannot_return_more_than_bought(db_session: Session, seeded: SeedCounts) -> None:
    o = order(db_session, "KO-1001")  # 2 tees + 1 jeans, delivered 10 days ago
    tees = o.items[0]
    with pytest.raises(APIError) as error:
        create_return(db_session, body_for(o, items=[{"order_item_id": tees.id, "quantity": 3}]), None,
                      ReturnCreatedBy.CUSTOMER, FIXED_NOW)
    assert error.value.code == "quantity_too_high"


def test_rule6_open_returns_use_up_the_quantity(db_session: Session, seeded: SeedCounts) -> None:
    o = order(db_session, "KO-1001")
    tees = o.items[0]
    create_return(db_session, body_for(o, items=[{"order_item_id": tees.id, "quantity": 1}]), None,
                  ReturnCreatedBy.CUSTOMER, FIXED_NOW)
    assert item_named(eligibility(db_session, "KO-1001"), "Everyday Cotton Tee").returnable_quantity == 1

    create_return(db_session, body_for(order(db_session, "KO-1001"), items=[{"order_item_id": tees.id, "quantity": 1}]),
                  None, ReturnCreatedBy.CUSTOMER, FIXED_NOW)
    entry = item_named(eligibility(db_session, "KO-1001"), "Everyday Cotton Tee")
    assert entry.returnable_quantity == 0
    assert entry.refusal and entry.refusal.code == "already_requested"


def test_rule6_rejected_returns_do_not_count(db_session: Session, seeded: SeedCounts) -> None:
    o = order(db_session, "KO-1001")
    request = create_return(db_session, body_for(o), None, ReturnCreatedBy.CUSTOMER, FIXED_NOW)
    request.status = ReturnStatus.REJECTED
    db_session.commit()
    assert item_named(eligibility(db_session, "KO-1001"), "Everyday Cotton Tee").returnable_quantity == 2


# --- rule 7: condition --------------------------------------------------------------------------


def test_rule7_condition_must_be_confirmed(db_session: Session, seeded: SeedCounts) -> None:
    o = order(db_session, "KO-1005")
    with pytest.raises(APIError) as error:
        create_return(db_session, body_for(o, condition_confirmed=False), None, ReturnCreatedBy.CUSTOMER, FIXED_NOW)
    assert error.value.code == "condition_not_confirmed"


# --- rule 8: return shipping --------------------------------------------------------------------


def test_rule8_us_gets_a_free_label_international_pays(db_session: Session, seeded: SeedCounts) -> None:
    assert eligibility(db_session, "KO-1005").return_shipping == "prepaid_label"
    o = order(db_session, "KO-1005")
    o.shipping_country = "GB"
    db_session.commit()
    assert eligibility(db_session, "KO-1005").return_shipping == "customer_pays"


# --- rule 9: exchanges --------------------------------------------------------------------------


def test_rule9_exchange_for_an_in_stock_size(db_session: Session, seeded: SeedCounts) -> None:
    o = order(db_session, "KO-1005")
    sweater = next(item for item in o.items if item.product_name.startswith("Merino"))
    options = item_named(eligibility(db_session, "KO-1005"), "Merino").exchange_options
    target = next(v for v in options if v.size == "M" and v.color == "Oatmeal")

    request = create_return(
        db_session,
        body_for(o, type="exchange", items=[{"order_item_id": sweater.id, "quantity": 1}], exchange_variant_id=target.id),
        None, ReturnCreatedBy.CUSTOMER, FIXED_NOW,
    )
    assert request.type is ReturnType.EXCHANGE
    assert request.exchange_details == f"Exchange for M / Oatmeal (SKU {target.sku})"


def test_rule9_exchange_needs_stock(db_session: Session, seeded: SeedCounts) -> None:
    o = order(db_session, "KO-1005")
    sweater = next(item for item in o.items if item.product_name.startswith("Merino"))
    options = item_named(eligibility(db_session, "KO-1005"), "Merino").exchange_options
    target = options[0]
    target.stock = 0
    db_session.commit()
    assert target.id not in [v.id for v in item_named(eligibility(db_session, "KO-1005"), "Merino").exchange_options]

    with pytest.raises(APIError) as error:
        create_return(
            db_session,
            body_for(order(db_session, "KO-1005"), type="exchange",
                     items=[{"order_item_id": sweater.id, "quantity": 1}], exchange_variant_id=target.id),
            None, ReturnCreatedBy.CUSTOMER, FIXED_NOW,
        )
    assert error.value.code == "exchange_unavailable"


def test_rule9_exchange_must_be_the_same_product(db_session: Session, seeded: SeedCounts) -> None:
    o = order(db_session, "KO-1005")
    sweater = next(item for item in o.items if item.product_name.startswith("Merino"))
    other_product = db_session.scalars(select(ProductVariant).where(ProductVariant.sku == "KO-001-WHIT-M")).one()
    with pytest.raises(APIError) as error:
        create_return(
            db_session,
            body_for(o, type="exchange", items=[{"order_item_id": sweater.id, "quantity": 1}],
                     exchange_variant_id=other_product.id),
            None, ReturnCreatedBy.CUSTOMER, FIXED_NOW,
        )
    assert error.value.code == "exchange_unavailable"


# --- creating a return ---------------------------------------------------------------------------


def test_return_request_is_saved_with_a_timeline_event(db_session: Session, seeded: SeedCounts) -> None:
    o = order(db_session, "KO-1005")
    request = create_return(db_session, body_for(o, comments="  Too big in the shoulders "), None,
                            ReturnCreatedBy.CUSTOMER, FIXED_NOW)
    assert request.status is ReturnStatus.REQUESTED
    assert request.reason == "Doesn't fit: Too big in the shoulders"
    assert returns.refund_estimate_cents(request) == 8900  # the sweater; shipping isn't refunded
    o = order(db_session, "KO-1005")
    assert o.status is OrderStatus.DELIVERED  # unchanged until the refund happens
    assert o.events[-1].note == "Return requested: 1 × Merino Crew Sweater."


def test_logged_in_customer_can_use_their_order_without_email(db_session: Session, seeded: SeedCounts, customer: User) -> None:
    o = order(db_session, "KO-1005")
    o.user_id = customer.id
    db_session.commit()
    assert find_order(db_session, "ko-1005", None, customer).order_number == "KO-1005"
    other = User(email="x@example.com", password_hash="x", name="X")
    db_session.add(other)
    db_session.commit()
    with pytest.raises(APIError):
        find_order(db_session, "KO-1005", None, other)


# --- the HTTP API (the phase's "done when") -------------------------------------------------------


def post(client: FlaskClient, path: str, body: dict[str, Any], **kwargs: Any) -> Any:
    return client.post(path, json=body, **kwargs)


def test_api_done_when(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    emails = {n: order(db_session, n).email for n in ("KO-1005", "KO-1007", "KO-1011")}

    ko_1005 = post(client, "/api/returns/eligibility", {"order_number": "KO-1005", "email": emails["KO-1005"]}).get_json()
    assert ko_1005["eligible"] is True
    assert ko_1005["days_left"] == 8 and ko_1005["return_shipping"] == "prepaid_label"

    ko_1007 = post(client, "/api/returns/eligibility", {"order_number": "KO-1007", "email": emails["KO-1007"]}).get_json()
    assert ko_1007["eligible"] is False
    assert ko_1007["reason"]["code"] == "window_closed"

    ko_1011 = post(client, "/api/returns/eligibility", {"order_number": "KO-1011", "email": emails["KO-1011"]}).get_json()
    socks = next(item for item in ko_1011["items"] if item["product_name"].startswith("Crew Socks"))
    assert socks["returnable_quantity"] == 0 and socks["reason"]["code"] == "final_sale"

    # And the refusal holds when someone tries anyway:
    response = post(client, "/api/returns", {
        "order_number": "KO-1011", "email": emails["KO-1011"], "type": "refund", "reason": "changed_mind",
        "items": [{"order_item_id": socks["order_item_id"], "quantity": 1}], "condition_confirmed": True,
    })
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "final_sale"


def test_api_create_return(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    o = order(db_session, "KO-1005")
    response = post(client, "/api/returns", {
        "order_number": "1005", "email": o.email.upper(), "type": "refund", "reason": "doesnt_fit",
        "items": [{"order_item_id": o.items[1].id, "quantity": 1}], "condition_confirmed": True,
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "requested"
    assert body["items"][0]["product_name"] == "Wool Beanie"
    assert body["refund_estimate_cents"] == 2200
    assert db_session.scalar(select(ReturnRequest.id).where(ReturnRequest.id == body["id"])) is not None


def test_api_logged_in_return_needs_csrf_but_no_email(
    logged_in: FlaskClient, db_session: Session, seeded: SeedCounts, customer: User
) -> None:
    o = order(db_session, "KO-1005")
    o.user_id = customer.id
    db_session.commit()
    body = {"order_number": "KO-1005", "type": "refund", "reason": "doesnt_fit",
            "items": [{"order_item_id": o.items[0].id, "quantity": 1}], "condition_confirmed": True}
    assert post(logged_in, "/api/returns", body).status_code == 403  # no CSRF header
    assert post(logged_in, "/api/returns", body, headers=csrf_headers(logged_in)).status_code == 201

    detail = logged_in.get("/api/account/orders/KO-1005").get_json()
    assert [r["status"] for r in detail["returns"]] == ["requested"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"type": "exchange"},  # exchange without a target
        {"exchange_variant_id": 5},  # target on a refund
        {"reason": "bored"},
        {"items": []},
    ],
)
def test_api_validation(client: FlaskClient, db_session: Session, seeded: SeedCounts, overrides: dict[str, Any]) -> None:
    o = order(db_session, "KO-1005")
    body = {"order_number": "KO-1005", "email": o.email, "type": "refund", "reason": "doesnt_fit",
            "items": [{"order_item_id": o.items[0].id, "quantity": 1}], "condition_confirmed": True}
    assert post(client, "/api/returns", body | overrides).status_code == 400


def test_days_left_rounds_up() -> None:
    deadline = FIXED_NOW + timedelta(days=8)
    assert returns.days_left(deadline, FIXED_NOW) == 8
    assert returns.days_left(deadline, FIXED_NOW + timedelta(seconds=5)) == 8  # not 7
    assert returns.days_left(deadline, FIXED_NOW + timedelta(days=7, hours=23)) == 1
    assert returns.days_left(deadline, FIXED_NOW + timedelta(days=9)) == 0
