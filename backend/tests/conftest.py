"""Shared pytest fixtures. Tests run against the kora_test Postgres database (docker compose)."""

from collections.abc import Iterator
from datetime import UTC, datetime

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
