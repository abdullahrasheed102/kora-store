"""Configuration, read from environment variables only.

Values are read when a config object is *instantiated* (inside create_app), not when this
module is imported, so tests can build configs without a populated environment.
"""

import os
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit


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


PAYMENT_PROVIDERS = {"sandbox", "stripe"}
# log: print emails to the log, send nothing (tests) · mailpit: deliver to the local Mailpit
# inbox at http://localhost:8025 (development) · resend: really send, through Resend's HTTP API.
EMAIL_PROVIDERS = {"log", "mailpit", "resend"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db"}  # "db": the docker compose service name
SAFE_SSL_MODES = {"require", "verify-ca", "verify-full"}
MIN_SECRET_LENGTH = 32
PLACEHOLDER_MARKERS = ("dev-only", "change-me", "changeme")


def engine_options(database_url: str) -> dict[str, Any]:
    """SQLAlchemy connection pool settings, tuned for Neon (serverless Postgres)."""
    connect_args: dict[str, Any] = {"connect_timeout": 10}  # a cold Neon compute wakes in ~1s
    host = urlsplit(database_url).hostname or ""
    if "-pooler." in host:
        # Neon's *pooled* endpoint is PgBouncer in transaction mode: consecutive queries may run
        # on different server connections. psycopg prepares statements it sees often, and a
        # prepared statement lives on ONE server connection, so turn that off to be safe.
        connect_args["prepare_threshold"] = None
    return {
        # Check each pooled connection before use: Neon closes idle connections when its
        # compute sleeps, and Render's free instance sleeps too. Without this, the first
        # request after a quiet period fails with "server closed the connection".
        "pool_pre_ping": True,
        "pool_recycle": 300,  # replace connections older than 5 minutes
        "pool_size": 5,  # one gunicorn worker with 4 threads needs at most ~4 at a time
        "max_overflow": 5,
        "connect_args": connect_args,
    }


class BaseConfig:
    DEBUG = False
    CHECKOUT_SESSION_MINUTES = 30  # Stripe's minimum; unpaid sessions expire after this
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
    SQLALCHEMY_ENGINE_OPTIONS: dict[str, Any] = {"pool_pre_ping": True}  # replaced per URL below
    DEFAULT_EMAIL_PROVIDER = "log"  # production must choose "resend" explicitly (render.yaml)

    def __init__(self) -> None:
        self.SECRET_KEY = require_env("SECRET_KEY")
        self.SQLALCHEMY_DATABASE_URI = normalize_database_url(require_env("DATABASE_URL"))
        self.SQLALCHEMY_ENGINE_OPTIONS = engine_options(self.SQLALCHEMY_DATABASE_URI)
        self.FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
        self.JWT_SECRET_KEY = require_env("JWT_SECRET_KEY")
        # In-memory counters work for one server process. With several workers or instances
        # they must be shared, e.g. RATELIMIT_STORAGE_URI=redis://...
        self.RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
        # How many proxies sit in front of Flask (Vercel + Render = 2). Needed to read the
        # real client IP for rate limiting. 0 = trust nothing (local development).
        self.TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))
        # --- Payments: "sandbox" (our fake provider, no real money) or "stripe" (test mode) ---
        self.PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "sandbox")
        if self.PAYMENT_PROVIDER not in PAYMENT_PROVIDERS:
            raise RuntimeError(f"PAYMENT_PROVIDER must be one of {sorted(PAYMENT_PROVIDERS)}")
        self.SANDBOX_WEBHOOK_SECRET = (
            require_env("SANDBOX_WEBHOOK_SECRET") if self.PAYMENT_PROVIDER == "sandbox" else ""
        )
        # --- Stripe (test mode only) ---
        self.STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
        self.STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        # Optional: point the Stripe client at stripe-mock (http://localhost:12111) for offline testing.
        self.STRIPE_API_BASE = os.environ.get("STRIPE_API_BASE", "")
        if self.STRIPE_SECRET_KEY.startswith(("sk_live_", "rk_live_")):
            # This is a demo store: refuse to start rather than risk charging real cards.
            raise RuntimeError("Live Stripe keys are not allowed. Use a test key (sk_test_...).")
        # Optional: `flask seed` creates the admin account from these when both are set.
        self.ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
        self.ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
        self._load_email_settings()

    def _load_email_settings(self) -> None:
        # --- Email (docs/guide/08a-email-notifications.md) ---
        self.EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", self.DEFAULT_EMAIL_PROVIDER)
        if self.EMAIL_PROVIDER not in EMAIL_PROVIDERS:
            raise RuntimeError(f"EMAIL_PROVIDER must be one of {sorted(EMAIL_PROVIDERS)}")
        self.EMAIL_FROM = os.environ.get("EMAIL_FROM", "Kora Outfitters <orders@kora.local>")
        self.RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
        self.RESEND_API_URL = os.environ.get("RESEND_API_URL", "https://api.resend.com")
        self.MAILPIT_SMTP_HOST = os.environ.get("MAILPIT_SMTP_HOST", "localhost")
        self.MAILPIT_SMTP_PORT = int(os.environ.get("MAILPIT_SMTP_PORT", "1025"))
        # Where new-ticket alerts go, and the Reply-To on customer emails (so replies reach a person).
        self.ADMIN_NOTIFY_EMAIL = os.environ.get("ADMIN_NOTIFY_EMAIL") or None
        # The scheduled retry job sends this as a Bearer token. Empty = the endpoint is switched off.
        self.OUTBOX_CRON_SECRET = os.environ.get("OUTBOX_CRON_SECRET", "")
        # Stay under Resend's free tier (100 emails a day) and stop one address being flooded.
        self.EMAIL_DAILY_CAP = int(os.environ.get("EMAIL_DAILY_CAP", "80"))
        self.EMAIL_RECIPIENT_DAILY_CAP = int(os.environ.get("EMAIL_RECIPIENT_DAILY_CAP", "10"))
        # True: send in a background thread after the commit, so nobody waits for the email
        # provider. Tests send inline instead, so they can check the result straight away.
        self.EMAIL_SEND_IN_BACKGROUND = True


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    JWT_COOKIE_SECURE = False  # http://localhost has no HTTPS
    # Locally, every email lands in Mailpit (docker compose) and nothing leaves your laptop.
    DEFAULT_EMAIL_PROVIDER = "mailpit"


class ProductionConfig(BaseConfig):
    def __init__(self) -> None:
        super().__init__()
        # Fail fast: refuse to start with settings that would be unsafe on the internet,
        # instead of discovering them later from a breach or a confused bug report.
        problems = production_problems(self)
        if problems:
            raise RuntimeError("Unsafe production settings:\n- " + "\n- ".join(problems))


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
        self.PAYMENT_PROVIDER = "sandbox"  # the default; Stripe tests switch it (tests/conftest.py)
        self.SANDBOX_WEBHOOK_SECRET = "sandbox_test_secret"
        # Fake values: tests replace every call to Stripe (see tests/conftest.py fake_stripe).
        self.STRIPE_SECRET_KEY = "sk_test_dummy"
        self.STRIPE_WEBHOOK_SECRET = "whsec_test_secret"
        self.STRIPE_API_BASE = ""
        self._load_email_settings()
        # Fixed values, so a developer's .env can't change what the tests expect.
        self.EMAIL_PROVIDER = "log"
        self.EMAIL_FROM = "Kora Outfitters <orders@kora.local>"
        self.ADMIN_NOTIFY_EMAIL = "owner@kora.local"
        self.OUTBOX_CRON_SECRET = "test-outbox-cron-secret"
        self.EMAIL_DAILY_CAP = 80
        self.EMAIL_RECIPIENT_DAILY_CAP = 10
        self.EMAIL_SEND_IN_BACKGROUND = False


def production_problems(config: BaseConfig) -> list[str]:
    """Every reason this config isn't safe to run in production (empty list = fine)."""
    problems = []
    secrets = {"SECRET_KEY": config.SECRET_KEY, "JWT_SECRET_KEY": config.JWT_SECRET_KEY}
    if config.PAYMENT_PROVIDER == "sandbox":
        secrets["SANDBOX_WEBHOOK_SECRET"] = config.SANDBOX_WEBHOOK_SECRET
    for name, value in secrets.items():
        if len(value) < MIN_SECRET_LENGTH or any(marker in value.lower() for marker in PLACEHOLDER_MARKERS):
            problems.append(f"{name} must be a random value of at least {MIN_SECRET_LENGTH} characters")

    if not config.FRONTEND_URL.startswith("https://"):
        problems.append("FRONTEND_URL must be an https:// URL (payment redirects go there)")

    url = urlsplit(config.SQLALCHEMY_DATABASE_URI)
    ssl_mode = parse_qs(url.query).get("sslmode", [""])[0]
    if url.hostname not in LOCAL_HOSTS and ssl_mode not in SAFE_SSL_MODES:
        # Without this, the password and all data could cross the internet unencrypted.
        problems.append("DATABASE_URL must end with ?sslmode=require (Neon's connection strings include it)")

    if config.PAYMENT_PROVIDER == "stripe" and not (config.STRIPE_SECRET_KEY and config.STRIPE_WEBHOOK_SECRET):
        problems.append("PAYMENT_PROVIDER=stripe needs STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET")

    if config.EMAIL_PROVIDER == "mailpit":
        problems.append("EMAIL_PROVIDER=mailpit is for local development; use resend (or log)")
    if config.EMAIL_PROVIDER == "resend":
        for name in ("RESEND_API_KEY", "EMAIL_FROM", "ADMIN_NOTIFY_EMAIL"):
            if not getattr(config, name):
                problems.append(f"EMAIL_PROVIDER=resend needs {name}")
    if config.OUTBOX_CRON_SECRET and len(config.OUTBOX_CRON_SECRET) < MIN_SECRET_LENGTH:
        problems.append(f"OUTBOX_CRON_SECRET must be a random value of at least {MIN_SECRET_LENGTH} characters")

    workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
    if config.RATELIMIT_STORAGE_URI.startswith("memory://") and workers > 1:
        # Each worker process would keep its own counters, multiplying every limit.
        problems.append("RATELIMIT_STORAGE_URI=memory:// only works with WEB_CONCURRENCY=1; use redis:// for more workers")
    return problems


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
