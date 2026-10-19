"""POST /api/cart/quote: the server prices the cart; the client's numbers are never trusted."""

from typing import Any

import pytest
from flask.testing import FlaskClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product, ProductVariant
from app.seed import SeedCounts


def variant(session: Session, sku: str) -> ProductVariant:
    return session.scalars(select(ProductVariant).where(ProductVariant.sku == sku)).one()


def quote(client: FlaskClient, items: list[dict[str, Any]], method: str | None = None, status: int = 200) -> Any:
    body: dict[str, Any] = {"items": items}
    if method:
        body["shipping_method"] = method
    response = client.post("/api/cart/quote", json=body)
    assert response.status_code == status, response.get_json()
    return response.get_json()


def test_prices_come_from_the_database(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    tee = variant(db_session, "KO-001-WHIT-M")  # $24
    # A tampered client sends its own price. It must be ignored.
    body = quote(client, [{"variant_id": tee.id, "quantity": 2, "price_cents": 1, "unit_price_cents": 1}])

    [line] = body["items"]
    assert line["unit_price_cents"] == 2400
    assert line["line_total_cents"] == 4800
    assert body["subtotal_cents"] == 4800
    assert body["shipping_cents"] == 695  # under $75
    assert body["total_cents"] == 5495
    assert body["amount_to_free_shipping_cents"] == 2701  # $75.01 - $48.00


def test_free_standard_shipping_over_75(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    tee = variant(db_session, "KO-001-WHIT-M")
    body = quote(client, [{"variant_id": tee.id, "quantity": 4}])  # $96
    assert body["shipping_cents"] == 0
    assert body["amount_to_free_shipping_cents"] == 0


@pytest.mark.parametrize(("method", "shipping"), [("express", 1495), ("international", 1995)])
def test_paid_shipping_methods(client: FlaskClient, db_session: Session, seeded: SeedCounts, method: str, shipping: int) -> None:
    tee = variant(db_session, "KO-001-WHIT-M")
    body = quote(client, [{"variant_id": tee.id, "quantity": 4}], method)
    assert body["shipping_cents"] == shipping
    assert body["amount_to_free_shipping_cents"] is None


def test_variant_price_override(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    gift = variant(db_session, "KO-020-DIGI-100")
    assert quote(client, [{"variant_id": gift.id, "quantity": 1}])["subtotal_cents"] == 10000


def test_repeated_lines_are_merged(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    tee = variant(db_session, "KO-001-WHIT-M")
    body = quote(client, [{"variant_id": tee.id, "quantity": 1}, {"variant_id": tee.id, "quantity": 2}])
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 3


def test_not_enough_stock_reduces_the_quantity(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    tee = variant(db_session, "KO-001-WHIT-M")
    tee.stock = 2
    db_session.commit()

    [line] = quote(client, [{"variant_id": tee.id, "quantity": 5}])["items"]
    assert (line["requested_quantity"], line["quantity"], line["issue"]) == (5, 2, "insufficient_stock")
    assert line["line_total_cents"] == 4800


def test_out_of_stock_and_unknown_items_cost_nothing(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    jogger = db_session.scalars(
        select(ProductVariant).join(Product).where(Product.slug == "everyday-joggers")
    ).first()
    assert jogger is not None and jogger.stock == 0

    body = quote(client, [{"variant_id": jogger.id, "quantity": 1}, {"variant_id": 999999, "quantity": 1}])
    assert [item["issue"] for item in body["items"]] == ["out_of_stock", "unavailable"]
    assert body["subtotal_cents"] == body["shipping_cents"] == body["total_cents"] == 0
    assert body["has_issues"] is True


def test_inactive_product_is_unavailable(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    tee = variant(db_session, "KO-001-WHIT-M")
    tee.product.is_active = False
    db_session.commit()
    assert quote(client, [{"variant_id": tee.id, "quantity": 1}])["items"][0]["issue"] == "unavailable"


def test_empty_cart(client: FlaskClient, seeded: SeedCounts) -> None:
    body = quote(client, [])
    assert body["items"] == []
    assert body["total_cents"] == 0


@pytest.mark.parametrize(
    "body",
    [
        {"items": [{"variant_id": 1, "quantity": 0}]},
        {"items": [{"variant_id": 1, "quantity": 11}]},
        {"items": [{"variant_id": "abc", "quantity": 1}]},
        {"items": [{"variant_id": 1, "quantity": 1}] * 51},
        {"items": [], "shipping_method": "teleport"},
        {"items": "everything"},
    ],
)
def test_invalid_quotes_are_400(client: FlaskClient, seeded: SeedCounts, body: dict[str, Any]) -> None:
    response = client.post("/api/cart/quote", json=body)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"


def test_oversized_body_is_rejected(client: FlaskClient, seeded: SeedCounts) -> None:
    response = client.post("/api/cart/quote", data="x" * 100_000, content_type="application/json")
    assert response.status_code == 413
