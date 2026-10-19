"""Configuration, read from environment variables only.

Values are read when a config object is *instantiated* (inside create_app), not when this
module is imported, so tests can build configs without a populated environment.
"""

import os
from datetime import timedelta
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
    MAX_CONTENT_LENGTH = 64 * 1024  # reject request bodies over 64 KB before reading them

    # --- Sessions: a JWT in an httpOnly cookie (see docs/guide/03-cart-and-auth.md) ---
    JWT_TOKEN_LOCATION = ["cookies"]  # never read tokens from headers or the URL
    JWT_COOKIE_SECURE = True  # cookie only sent over HTTPS (relaxed in development)
    JWT_COOKIE_SAMESITE = "Lax"  # not sent on cross-site POSTs, sent on normal link clicks
    JWT_COOKIE_CSRF_PROTECT = True  # POST/PUT/PATCH/DELETE need the X-CSRF-TOKEN header
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)
    JWT_SESSION_COOKIE = False  # keep the cookie after the browser closes, until it expires

    # --- Rate limiting ---
    RATELIMIT_HEADERS_ENABLED = True  # send Retry-After so clients know when to try again
    # Check each pooled connection before use. Neon closes idle connections and Render sleeps,
    # so without this the first request after a quiet period fails with a dead connection.
    SQLALCHEMY_ENGINE_OPTIONS: dict[str, Any] = {"pool_pre_ping": True}

    def __init__(self) -> None:
        self.SECRET_KEY = require_env("SECRET_KEY")
        self.SQLALCHEMY_DATABASE_URI = normalize_database_url(require_env("DATABASE_URL"))
        self.FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
        self.JWT_SECRET_KEY = require_env("JWT_SECRET_KEY")
        # In-memory counters work for one server process. With several workers or instances
        # they must be shared, e.g. RATELIMIT_STORAGE_URI=redis://...
        self.RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
        # How many proxies sit in front of Flask (Vercel + Render = 2). Needed to read the
        # real client IP for rate limiting. 0 = trust nothing (local development).
        self.TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))
        # Optional: `flask seed` creates the admin account from these when both are set.
        self.ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
        self.ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    JWT_COOKIE_SECURE = False  # http://localhost has no HTTPS


class ProductionConfig(BaseConfig):
    pass


class TestingConfig(BaseConfig):
    TESTING = True
    JWT_COOKIE_SECURE = False  # the test client uses plain http

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
        self.JWT_SECRET_KEY = "test-jwt-secret-key-at-least-32-bytes-long"
        self.RATELIMIT_STORAGE_URI = "memory://"
        self.TRUSTED_PROXY_COUNT = 0
        self.ADMIN_EMAIL = None
        self.ADMIN_PASSWORD = None


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
