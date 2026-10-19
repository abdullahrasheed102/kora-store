"""Catalog endpoints: /api/products, /api/products/<slug>, /api/categories, /api/policies."""

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.catalog import escape_like, size_sort_key, slugify
from app.extensions import db
from app.models import Order, OrderStatus, Product
from app.seed import SeedCounts
from tests.factories import make_product, make_variant


def get_json(client: FlaskClient, url: str, status: int = 200) -> Any:
    response = client.get(url)
    assert response.status_code == status, response.get_json()
    return response.get_json()


def slugs(body: dict[str, Any]) -> list[str]:
    return [item["slug"] for item in body["items"]]


# --- listing and pagination -------------------------------------------------------------------


def test_list_returns_first_page_with_totals(client: FlaskClient, seeded: SeedCounts) -> None:
    body = get_json(client, "/api/products")
    assert len(body["items"]) == 12
    assert (body["page"], body["per_page"], body["total"], body["total_pages"]) == (1, 12, 20, 2)


def test_second_page_has_the_rest_without_repeats(client: FlaskClient, seeded: SeedCounts) -> None:
    first = slugs(get_json(client, "/api/products?page=1"))
    second = slugs(get_json(client, "/api/products?page=2"))
    assert len(second) == 8
    assert not set(first) & set(second)


def test_page_past_the_end_is_empty_not_an_error(client: FlaskClient, seeded: SeedCounts) -> None:
    body = get_json(client, "/api/products?page=9")
    assert body["items"] == []
    assert body["total"] == 20


def test_product_card_fields(client: FlaskClient, seeded: SeedCounts) -> None:
    body = get_json(client, "/api/products?q=gift")
    [card] = body["items"]
    assert card == {
        "slug": "gift-card",
        "name": "Gift Card",
        "category": "Gift Cards",
        "category_slug": "gift-cards",
        "price_cents": 2500,
        "price_min_cents": 2500,
        "price_max_cents": 10000,
        "image_url": None,
        "is_final_sale": True,
        "in_stock": True,
        "colors": ["Digital"],
    }


def test_inactive_products_are_hidden(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    tee = db_session.scalars(select(Product).filter_by(slug="everyday-cotton-tee")).one()
    tee.is_active = False
    db_session.commit()

    assert "everyday-cotton-tee" not in slugs(get_json(client, "/api/products?per_page=48"))
    get_json(client, "/api/products/everyday-cotton-tee", status=404)


# --- filters ----------------------------------------------------------------------------------


def test_filter_by_category_slug(client: FlaskClient, seeded: SeedCounts) -> None:
    body = get_json(client, "/api/products?category=tops")
    assert body["total"] == 5
    assert {item["category"] for item in body["items"]} == {"Tops"}


def test_unknown_category_is_404(client: FlaskClient, seeded: SeedCounts) -> None:
    body = get_json(client, "/api/products?category=hats", status=404)
    assert body["error"]["code"] == "category_not_found"


@pytest.mark.parametrize("q", ["linen", "LINEN", "  linen  "])
def test_search_is_case_insensitive_and_trimmed(client: FlaskClient, seeded: SeedCounts, q: str) -> None:
    assert slugs(get_json(client, f"/api/products?q={q}")) == ["linen-button-up-shirt"]


def test_search_matches_description(client: FlaskClient, seeded: SeedCounts) -> None:
    assert slugs(get_json(client, "/api/products?q=laptop")) == ["canvas-tote-bag"]


def test_search_wildcards_are_literal(client: FlaskClient, seeded: SeedCounts) -> None:
    # Unescaped, "%" would match every product.
    assert get_json(client, "/api/products?q=%25")["total"] == 0


def test_size_filter_accepts_several_values(client: FlaskClient, seeded: SeedCounts) -> None:
    body = get_json(client, "/api/products?size=US 10&size=One size&per_page=48")
    assert set(slugs(body)) == {"classic-sneakers", "chelsea-boots", "canvas-tote-bag", "wool-beanie"}


def test_size_and_color_must_match_the_same_variant(client: FlaskClient, db_session: Session) -> None:
    product = make_product(db_session)
    make_variant(db_session, product, sku="A", size="M", color="White")
    make_variant(db_session, product, sku="B", size="L", color="Black")
    db_session.commit()

    assert get_json(client, "/api/products?size=M&color=Black")["total"] == 0
    assert get_json(client, "/api/products?size=M&color=White")["total"] == 1


def test_size_filter_ignores_out_of_stock_variants(client: FlaskClient, db_session: Session) -> None:
    product = make_product(db_session)
    make_variant(db_session, product, sku="A", size="M", stock=0)
    make_variant(db_session, product, sku="B", size="L", stock=3)
    db_session.commit()

    assert get_json(client, "/api/products?size=M")["total"] == 0
    assert get_json(client, "/api/products?size=L")["total"] == 1


def test_price_range_filter(client: FlaskClient, seeded: SeedCounts) -> None:
    body = get_json(client, "/api/products?min_price=5000&max_price=9000&per_page=48")
    assert body["total"] > 0
    assert all(5000 <= item["price_cents"] <= 9000 for item in body["items"])


def test_facets_ignore_the_size_filter_but_follow_the_category(client: FlaskClient, seeded: SeedCounts) -> None:
    body = get_json(client, "/api/products?category=bottoms&size=28")
    facets = body["facets"]
    assert "30" in facets["sizes"]  # still offered while 28 is selected
    assert "US 10" not in facets["sizes"]  # shoes aren't bottoms
    assert facets["sizes"] == sorted(facets["sizes"], key=size_sort_key)


# --- sorting ----------------------------------------------------------------------------------


@pytest.mark.parametrize(("sort", "reverse"), [("price_asc", False), ("price_desc", True)])
def test_sort_by_price(client: FlaskClient, seeded: SeedCounts, sort: str, reverse: bool) -> None:
    prices = [item["price_cents"] for item in get_json(client, f"/api/products?sort={sort}&per_page=48")["items"]]
    assert prices == sorted(prices, reverse=reverse)


def test_sort_by_name(client: FlaskClient, seeded: SeedCounts) -> None:
    names = [item["name"] for item in get_json(client, "/api/products?sort=name_asc&per_page=48")["items"]]
    assert names == sorted(names)


def test_best_selling_counts_only_completed_orders(
    client: FlaskClient, db_session: Session, seeded: SeedCounts
) -> None:
    units: Counter[str] = Counter()
    for order in db_session.scalars(select(Order)):
        if order.status in (OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED):
            continue
        for item in order.items:
            assert item.variant is not None
            units[item.variant.product.slug] += item.quantity

    listed = slugs(get_json(client, "/api/products?per_page=48"))
    assert [units[slug] for slug in listed] == sorted(units.values(), reverse=True) + [0] * (20 - len(units))


# --- validation -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    ["page=0", "page=abc", "per_page=100", "sort=random", "min_price=-1", "min_price=500&max_price=100"],
)
def test_bad_query_parameters_are_400(client: FlaskClient, seeded: SeedCounts, query: str) -> None:
    body = get_json(client, f"/api/products?{query}", status=400)
    assert body["error"]["code"] == "validation_error"


def test_empty_parameters_are_ignored(client: FlaskClient, seeded: SeedCounts) -> None:
    assert get_json(client, "/api/products?q=&category=&size=")["total"] == 20


# --- performance: no N+1 queries ----------------------------------------------------------------


@contextmanager
def count_queries(app: Flask) -> Iterator[list[str]]:
    statements: list[str] = []

    def record(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        statements.append(statement)

    with app.app_context():
        engine = db.engine
    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_listing_uses_the_same_number_of_queries_for_any_page_size(
    app: Flask, client: FlaskClient, seeded: SeedCounts
) -> None:
    with count_queries(app) as small:
        client.get("/api/products?per_page=2")
    with count_queries(app) as large:
        client.get("/api/products?per_page=20")
    # If variants were lazy-loaded per product, the large page would run ~18 more queries.
    assert len(small) == len(large)


# --- product detail ---------------------------------------------------------------------------


def test_product_detail(client: FlaskClient, seeded: SeedCounts) -> None:
    body = get_json(client, "/api/products/everyday-cotton-tee")
    assert body["name"] == "Everyday Cotton Tee"
    assert body["sizes"] == ["XS", "S", "M", "L", "XL", "XXL"]
    assert len(body["variants"]) == 18
    variant = body["variants"][0]
    assert set(variant) == {"id", "sku", "size", "color", "stock", "price_cents", "in_stock"}


def test_variant_prices_include_overrides(client: FlaskClient, seeded: SeedCounts) -> None:
    body = get_json(client, "/api/products/gift-card")
    assert {v["size"]: v["price_cents"] for v in body["variants"]} == {"$25": 2500, "$50": 5000, "$100": 10000}
    assert body["sizes"] == ["$25", "$50", "$100"]


def test_out_of_stock_product_shows_restock_note(client: FlaskClient, seeded: SeedCounts) -> None:
    body = get_json(client, "/api/products/everyday-joggers")
    assert body["in_stock"] is False
    assert body["restock_note"] == "Restock expected in about 3 weeks"


def test_related_products_share_the_category(client: FlaskClient, seeded: SeedCounts) -> None:
    body = get_json(client, "/api/products/everyday-cotton-tee")
    assert len(body["related"]) == 4
    assert all(item["category"] == "Tops" for item in body["related"])
    assert "everyday-cotton-tee" not in slugs({"items": body["related"]})


def test_unknown_product_is_404(client: FlaskClient, seeded: SeedCounts) -> None:
    assert get_json(client, "/api/products/nope", status=404)["error"]["code"] == "product_not_found"


# --- categories and policies --------------------------------------------------------------------


def test_categories_in_display_order_with_counts(client: FlaskClient, seeded: SeedCounts) -> None:
    body = get_json(client, "/api/categories")
    assert [c["slug"] for c in body] == ["tops", "bottoms", "outerwear", "footwear", "accessories", "gift-cards"]
    assert sum(c["product_count"] for c in body) == 20


def test_policies(client: FlaskClient, seeded: SeedCounts) -> None:
    body = get_json(client, "/api/policies")
    assert [p["key"] for p in body] == ["shipping", "returns", "refunds", "cancellations", "support_hours"]
    assert get_json(client, "/api/policies/returns")["title"] == "Returns & exchanges"
    assert get_json(client, "/api/policies/nope", status=404)["error"]["code"] == "policy_not_found"


# --- helpers ------------------------------------------------------------------------------------


def test_helpers() -> None:
    assert slugify("Gift Cards") == "gift-cards"
    assert escape_like("50%_off") == "50\\%\\_off"
    assert sorted(["US 10", "US 7", "M", "XS", "One size", "$100", "$25", "30", "28"], key=size_sort_key) == [
        "XS", "M", "28", "30", "US 7", "US 10", "$25", "$100", "One size",
    ]
