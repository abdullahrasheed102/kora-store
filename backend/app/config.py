"""Configuration, read from environment variables only.

Values are read when a config object is *instantiated* (inside create_app), not when this
module is imported, so tests can build configs without a populated environment.
"""

import os
from typing import Any


def require_env(name: str) -> str:
    """Return an environment variable, failing fast at startup if it is missing."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def normalize_database_url(url: str) -> str:
    """Point SQLAlchemy at the psycopg 3 driver.

    Neon and Render hand out `postgresql://` (or legacy `postgres://`) URLs, which SQLAlchemy
    would map to psycopg2. We install psycopg 3, whose dialect name is `postgresql+psycopg`.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


class BaseConfig:
    DEBUG = False
    TESTING = False
    JSON_SORT_KEYS = False
    # Check each pooled connection before use. Neon closes idle connections and Render sleeps,
    # so without this the first request after a quiet period fails with a dead connection.
    SQLALCHEMY_ENGINE_OPTIONS: dict[str, Any] = {"pool_pre_ping": True}

    def __init__(self) -> None:
        self.SECRET_KEY = require_env("SECRET_KEY")
        self.SQLALCHEMY_DATABASE_URI = normalize_database_url(require_env("DATABASE_URL"))
        self.FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    pass


class TestingConfig(BaseConfig):
    TESTING = True

    def __init__(self) -> None:
        # Deliberately ignores DATABASE_URL: tests drop and recreate tables, so they must
        # never be able to reach the dev (or production) database by accident.
        self.SECRET_KEY = "test-secret-key"
        self.SQLALCHEMY_DATABASE_URI = normalize_database_url(
            os.environ.get(
                "TEST_DATABASE_URL", "postgresql://kora:kora@localhost:5432/kora_test"
            )
        )
        self.FRONTEND_URL = "http://localhost:3000"


CONFIGS: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def config_from_env() -> BaseConfig:
    """Pick the config class from APP_ENV. Defaults to production so debug is opt-in."""
    env = os.environ.get("APP_ENV", "production")
    try:
        return CONFIGS[env]()
    except KeyError:
        raise RuntimeError(f"Unknown APP_ENV {env!r}; expected one of {sorted(CONFIGS)}")
