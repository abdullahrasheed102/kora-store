"""Shared pytest fixtures. Tests run against the kora_test Postgres database (docker compose)."""

from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.config import TestingConfig


@pytest.fixture
def app() -> Iterator[Flask]:
    app = create_app(TestingConfig())
    yield app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def unreachable_db_client() -> FlaskClient:
    """A client whose database URL points at a closed port, to simulate the DB being down."""
    config = TestingConfig()
    config.SQLALCHEMY_DATABASE_URI = (
        "postgresql+psycopg://kora:kora@127.0.0.1:1/kora_test?connect_timeout=2"
    )
    return create_app(config).test_client()
