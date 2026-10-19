"""Shared pytest fixtures. Tests run against the kora_test Postgres database (docker compose)."""

import hashlib
import hmac
import json
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from flask_migrate import upgrade
from sqlalchemy import text
from sqlalchemy.orm import scoped_session

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User
from app.payments import StripeProvider
from app.security import hash_password
from app.seed import SeedCounts, reset_database, seed_database
from tests.factories import make_user

# A fixed "now" makes seed dates predictable in assertions.
FIXED_NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
ADMIN_EMAIL = "admin@kora.test"
ADMIN_PASSWORD = "test-admin-password"


@pytest.fixture(scope="session")
def _migrated_database() -> None:
    """Once per test run: wipe kora_test and build it with the real Alembic migrations.

    Using the migrations (not db.create_all()) means the tests also prove the migrations work.
    """
    app = create_app(TestingConfig())
    with app.app_context():
        with db.engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        upgrade()
        db.engine.dispose()


@pytest.fixture
def app(_migrated_database: None) -> Iterator[Flask]:
    app = create_app(TestingConfig())
    yield app
    with app.app_context():
        db.engine.dispose()  # close this app's connection pool so connections don't pile up


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def db_session(app: Flask) -> Iterator[scoped_session]:
    """A database session inside an app context. Every table is emptied afterwards."""
    with app.app_context():
        yield db.session
        db.session.rollback()  # in case the test left a failed transaction open
        reset_database(db.session)


@pytest.fixture
def seeded(db_session: scoped_session) -> SeedCounts:
    return seed_database(
        db_session, now=FIXED_NOW, admin_email=ADMIN_EMAIL, admin_password=ADMIN_PASSWORD
    )


@pytest.fixture
def unreachable_db_client() -> FlaskClient:
    """A client whose database URL points at a closed port, to simulate the DB being down."""
    config = TestingConfig()
    config.SQLALCHEMY_DATABASE_URI = (
        "postgresql+psycopg://kora:kora@127.0.0.1:1/kora_test?connect_timeout=2"
    )
    return create_app(config).test_client()


# --- auth helpers ----------------------------------------------------------------------------

CUSTOMER_EMAIL = "sam@example.com"
CUSTOMER_PASSWORD = "correct-horse-battery"


def csrf_headers(client: FlaskClient) -> dict[str, str]:
    """The header a real frontend sends: the readable CSRF cookie copied into X-CSRF-TOKEN."""
    cookie = client.get_cookie("csrf_access_token")
    return {"X-CSRF-TOKEN": cookie.value} if cookie else {}


@pytest.fixture
def customer(db_session: scoped_session) -> User:
    user = make_user(db_session, email=CUSTOMER_EMAIL, password_hash=hash_password(CUSTOMER_PASSWORD), name="Sam")
    db_session.commit()
    return user


@pytest.fixture
def logged_in(client: FlaskClient, customer: User) -> FlaskClient:
    response = client.post("/api/auth/login", json={"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD})
    assert response.status_code == 200, response.get_json()
    return client


# --- Stripe fakes ------------------------------------------------------------------------------


class FakeStripe:
    """Stands in for app.payments' network calls and records what they were asked to do."""

    def __init__(self) -> None:
        self.sessions: list[dict[str, Any]] = []
        self.refunds: list[str] = []
        self.refund_amounts: list[int | None] = []  # None = full refund
        self.fail_checkout = False
        self.fail_refund = False

    def create_checkout_session(self, params: dict[str, Any], idempotency_key: str) -> tuple[str, str]:
        if self.fail_checkout:
            raise ConnectionError("Stripe is down")
        session_id = f"cs_test_{len(self.sessions) + 1}"
        self.sessions.append({"id": session_id, "params": params, "idempotency_key": idempotency_key})
        return session_id, f"https://checkout.stripe.test/c/pay/{session_id}"

    def refund_payment(self, payment_intent_id: str, idempotency_key: str, amount_cents: int | None = None) -> None:
        if self.fail_refund:
            raise ConnectionError("Stripe is down")
        self.refunds.append(payment_intent_id)
        self.refund_amounts.append(amount_cents)


@pytest.fixture
def fake_stripe(app: Flask, monkeypatch: pytest.MonkeyPatch) -> FakeStripe:
    """Use the Stripe provider, with its two network calls replaced by a recording fake."""
    fake = FakeStripe()
    app.config["PAYMENT_PROVIDER"] = "stripe"
    monkeypatch.setattr(StripeProvider, "_create_session", lambda _self, params, key: fake.create_checkout_session(params, key))
    monkeypatch.setattr(StripeProvider, "_create_refund", lambda _self, pi, key, amount: fake.refund_payment(pi, key, amount))
    return fake


def sign_stripe_payload(payload: str, secret: str = "whsec_test_secret", timestamp: int | None = None) -> str:
    """Build a Stripe-Signature header exactly like Stripe does: HMAC-SHA256 of "<t>.<body>"."""
    t = timestamp if timestamp is not None else int(time.time())
    signature = hmac.new(secret.encode(), f"{t}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={t},v1={signature}"


def send_stripe_event(client: FlaskClient, event: dict[str, Any], **sign_kwargs: Any) -> Any:
    payload = json.dumps(event)
    return client.post(
        "/api/stripe/webhook",
        data=payload,
        content_type="application/json",
        headers={"Stripe-Signature": sign_stripe_payload(payload, **sign_kwargs)},
    )


@pytest.fixture
def admin_user(db_session: scoped_session) -> User:
    from app.models import UserRole

    user = make_user(db_session, email="boss@example.com", password_hash=hash_password("admin-password-123"),
                     name="Store Admin", role=UserRole.ADMIN)
    db_session.commit()
    return user


@pytest.fixture
def admin_client(app: Flask, admin_user: User) -> FlaskClient:
    """A separate client logged in as an admin (so tests can use it next to `logged_in`)."""
    client = app.test_client()
    response = client.post("/api/auth/login", json={"email": "boss@example.com", "password": "admin-password-123"})
    assert response.status_code == 200, response.get_json()
    return client
