"""What the homepage reads: product tags, policy summaries, and the newsletter sign-up."""

from typing import Any

from flask.testing import FlaskClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import NewsletterSubscriber, Product
from app.pricing import FREE_SHIPPING_THRESHOLD_CENTS
from app.returns import RETURN_WINDOW
from app.seed import SeedCounts
from tests.conftest import csrf_headers


def call(client: FlaskClient, method: str, path: str, body: Any = None) -> Any:
    return client.open(path, method=method, json=body, headers=csrf_headers(client))


def slugs(client: FlaskClient, query: str) -> set[str]:
    return {item["slug"] for item in client.get(f"/api/products?per_page=48&{query}").get_json()["items"]}


# --- tags -----------------------------------------------------------------------------------------


def test_the_seed_tags_every_homepage_section(client: FlaskClient, seeded: SeedCounts) -> None:
    assert len(slugs(client, "tag=new")) >= 6  # enough to scroll
    assert slugs(client, "tag=autumn-edit") == {"wool-blend-overcoat", "merino-crew-sweater", "chelsea-boots"}
    assert len(slugs(client, "tag=bestseller")) >= 4


def test_tag_combines_with_category_and_shows_on_cards(client: FlaskClient, seeded: SeedCounts) -> None:
    assert slugs(client, "tag=new&category=outerwear") == {
        "quilted-puffer-jacket", "wool-blend-overcoat", "lightweight-rain-shell"
    }
    card = client.get("/api/products?q=overcoat").get_json()["items"][0]
    assert card["tags"] == ["new", "autumn-edit"]


def test_tag_facets_only_cover_tagged_products(client: FlaskClient, seeded: SeedCounts) -> None:
    facets = client.get("/api/products?tag=autumn-edit").get_json()["facets"]
    assert "Camel" in facets["colors"] and "White" not in facets["colors"]  # no white in the edit


def test_unknown_tag_is_empty_and_bad_tag_is_refused(client: FlaskClient, seeded: SeedCounts) -> None:
    assert client.get("/api/products?tag=spring").get_json()["total"] == 0
    assert client.get("/api/products?tag=Not%20A%20Tag").status_code == 400


def test_admin_tags_are_cleaned_and_saved(admin_client: FlaskClient, client: FlaskClient, db_session: Session,
                                          seeded: SeedCounts) -> None:
    tee = db_session.scalars(select(Product).where(Product.slug == "everyday-cotton-tee")).one()
    response = call(admin_client, "PATCH", f"/api/admin/products/{tee.id}",
                    {"tags": [" Autumn Edit ", "new", "NEW", ""]})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["tags"] == ["autumn-edit", "new"]
    assert "everyday-cotton-tee" in slugs(client, "tag=autumn-edit")  # the homepage follows the edit

    bad = call(admin_client, "PATCH", f"/api/admin/products/{tee.id}", {"tags": ["sale!"]})
    assert bad.status_code == 400


def test_a_new_product_can_be_created_with_tags(admin_client: FlaskClient, seeded: SeedCounts) -> None:
    body = {"slug": "linen-trousers", "name": "Linen Trousers", "category": "Bottoms", "description": "Cool.",
            "price_cents": 6800, "tags": ["new"]}
    response = call(admin_client, "POST", "/api/admin/products", body)
    assert response.status_code == 201, response.get_json()
    assert response.get_json()["tags"] == ["new"]


# --- policy summaries (the perks strip) --------------------------------------------------------------


def test_policy_summaries_match_the_rules_the_code_enforces(client: FlaskClient, seeded: SeedCounts) -> None:
    """The perks strip shows these summaries; the checkout and returns code use the constants.
    If someone changes one without the other, this test fails instead of the site lying."""
    policies = {p["key"]: p for p in client.get("/api/policies").get_json()}
    assert f"${FREE_SHIPPING_THRESHOLD_CENTS // 100}" in policies["shipping"]["summary"]
    assert f"{RETURN_WINDOW.days} days" in policies["returns"]["summary"]
    assert "24/7" in policies["support_hours"]["summary"]


def test_admin_can_edit_and_clear_a_summary(admin_client: FlaskClient, client: FlaskClient, seeded: SeedCounts) -> None:
    body = {"title": "Shipping", "body": "Free US shipping on orders over $75.", "summary": "  Free shipping over $75 "}
    assert call(admin_client, "PUT", "/api/admin/policies/shipping", body).status_code == 200
    assert client.get("/api/policies/shipping").get_json()["summary"] == "Free shipping over $75"

    call(admin_client, "PUT", "/api/admin/policies/shipping", {**body, "summary": " "})
    assert client.get("/api/policies/shipping").get_json()["summary"] is None


# --- newsletter -------------------------------------------------------------------------------------


def subscribers(session: Session) -> list[str]:
    return list(session.scalars(select(NewsletterSubscriber.email).order_by(NewsletterSubscriber.id)))


def test_subscribe_stores_the_email_lowercase(client: FlaskClient, db_session: Session) -> None:
    response = client.post("/api/newsletter", json={"email": "  Sam@Example.com "})
    assert response.status_code == 200
    assert "Thanks for subscribing" in response.get_json()["message"]
    assert subscribers(db_session) == ["sam@example.com"]


def test_subscribing_twice_is_harmless_and_looks_the_same(client: FlaskClient, db_session: Session) -> None:
    first = client.post("/api/newsletter", json={"email": "sam@example.com"})
    second = client.post("/api/newsletter", json={"email": "SAM@example.com"})
    # Same status and message: the form doesn't reveal who is already subscribed.
    assert (first.status_code, first.get_json()) == (second.status_code, second.get_json())
    assert db_session.scalar(select(func.count()).select_from(NewsletterSubscriber)) == 1


def test_bad_input_is_refused(client: FlaskClient, db_session: Session) -> None:
    assert client.post("/api/newsletter", json={"email": "not-an-email"}).status_code == 400
    assert client.post("/api/newsletter", json={}).status_code == 400
    assert client.post("/api/newsletter", data="email=sam@example.com").status_code == 415  # JSON only
    assert subscribers(db_session) == []


def test_newsletter_is_rate_limited(client: FlaskClient, db_session: Session) -> None:
    statuses = [client.post("/api/newsletter", json={"email": f"p{i}@example.com"}).status_code for i in range(6)]
    assert statuses == [200] * 5 + [429]
