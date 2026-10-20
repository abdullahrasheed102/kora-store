"""Cloudflare Turnstile on guest checkout: verified on the server, guests only, failing closed."""

from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import turnstile
from app.models import Order, ProductVariant
from app.seed import SeedCounts
from tests.conftest import CUSTOMER_EMAIL, CUSTOMER_PASSWORD, csrf_headers
from tests.test_checkout import checkout_body
from tests.test_cod import cod_body


class FakeCloudflare:
    """Answers siteverify like Cloudflare does, and records what it was asked."""

    def __init__(self) -> None:
        self.requests: list[dict[str, list[str]]] = []
        self.answer: dict[str, Any] = {"success": True, "action": "checkout", "hostname": "localhost"}
        self.down = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("no route to Cloudflare", request=request)
        assert str(request.url) == turnstile.SITEVERIFY_URL
        self.requests.append(parse_qs(request.content.decode()))
        return httpx.Response(200, json=self.answer)


@pytest.fixture
def cloudflare(app: Flask, monkeypatch: pytest.MonkeyPatch) -> FakeCloudflare:
    fake = FakeCloudflare()
    app.config["TURNSTILE_SECRET_KEY"] = "0x4AAAAAAAtest-secret"
    monkeypatch.setattr(turnstile, "transport", httpx.MockTransport(fake.handler))
    return fake


@pytest.fixture
def tee(db_session: Session, seeded: SeedCounts) -> ProductVariant:
    return db_session.scalars(select(ProductVariant).where(ProductVariant.sku == "KO-001-WHIT-M")).one()


def orders(session: Session) -> int:
    session.expire_all()
    return session.scalar(select(func.count()).select_from(Order)) or 0


def items(tee: ProductVariant) -> list[dict[str, int]]:
    return [{"variant_id": tee.id, "quantity": 1}]


def test_a_guest_needs_a_token(client: FlaskClient, db_session: Session, tee: ProductVariant,
                               cloudflare: FakeCloudflare) -> None:
    before = orders(db_session)
    response = client.post("/api/checkout/cod", json=cod_body(items(tee)))
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "bot_check_required"
    assert orders(db_session) == before and cloudflare.requests == []  # refused before anything happens


def test_a_valid_token_lets_the_guest_order(client: FlaskClient, db_session: Session, tee: ProductVariant,
                                            cloudflare: FakeCloudflare) -> None:
    response = client.post("/api/checkout/cod", json=cod_body(items(tee), turnstile_token="token-from-widget"),
                           environ_base={"REMOTE_ADDR": "203.0.113.7"})
    assert response.status_code == 201, response.get_json()
    [sent] = cloudflare.requests
    assert sent == {"secret": ["0x4AAAAAAAtest-secret"], "response": ["token-from-widget"], "remoteip": ["203.0.113.7"]}


def test_card_checkout_is_protected_too(client: FlaskClient, db_session: Session, tee: ProductVariant,
                                        cloudflare: FakeCloudflare) -> None:
    assert client.post("/api/checkout/session", json=checkout_body(items(tee))).status_code == 400
    response = client.post("/api/checkout/session", json=checkout_body(items(tee), turnstile_token="t"))
    assert response.status_code == 201, response.get_json()


@pytest.mark.parametrize("answer", [
    {"success": False, "error-codes": ["invalid-input-response"]},
    {"success": False, "error-codes": ["timeout-or-duplicate"]},  # expired, or already used once
    {"success": True, "action": "login"},  # solved on a different page
])
def test_a_bad_token_is_refused(client: FlaskClient, db_session: Session, tee: ProductVariant,
                                cloudflare: FakeCloudflare, answer: dict[str, Any]) -> None:
    cloudflare.answer = answer
    before = orders(db_session)
    response = client.post("/api/checkout/cod", json=cod_body(items(tee), turnstile_token="t"))
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "bot_check_failed"
    assert orders(db_session) == before


def test_if_cloudflare_is_unreachable_guest_orders_fail_closed(client: FlaskClient, db_session: Session,
                                                               tee: ProductVariant, cloudflare: FakeCloudflare) -> None:
    cloudflare.down = True
    response = client.post("/api/checkout/cod", json=cod_body(items(tee), turnstile_token="t"))
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "bot_check_unavailable"


def test_logged_in_customers_skip_the_check(client: FlaskClient, db_session: Session, tee: ProductVariant,
                                            cloudflare: FakeCloudflare, customer: object) -> None:
    client.post("/api/auth/login", json={"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD})
    response = client.post("/api/checkout/cod", json=cod_body(items(tee)), headers=csrf_headers(client))
    assert response.status_code == 201, response.get_json()
    assert cloudflare.requests == []


def test_with_no_secret_configured_the_check_is_off(client: FlaskClient, db_session: Session,
                                                    tee: ProductVariant) -> None:
    # The test config's default; production refuses to start without a secret (test_email_outbox.py).
    assert client.post("/api/checkout/cod", json=cod_body(items(tee))).status_code == 201
