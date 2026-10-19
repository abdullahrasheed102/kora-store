"""Config loading from environment variables."""

import pytest

NEON_URL = "postgresql://user:pw@ep-cool-lab-123456-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
GOOD_PRODUCTION_ENV = {
    "APP_ENV": "production",
    "SECRET_KEY": "a" * 64,
    "JWT_SECRET_KEY": "b" * 64,
    "SANDBOX_WEBHOOK_SECRET": "c" * 64,
    "DATABASE_URL": NEON_URL,
    "FRONTEND_URL": "https://kora-outfitters.vercel.app",
    "PAYMENT_PROVIDER": "sandbox",
    "RATELIMIT_STORAGE_URI": "memory://",
    "WEB_CONCURRENCY": "1",
}


@pytest.fixture
def production_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """A complete, safe production environment. Tests change one value to make it unsafe."""
    for name, value in GOOD_PRODUCTION_ENV.items():
        monkeypatch.setenv(name, value)
    return monkeypatch

from app.config import DevelopmentConfig, ProductionConfig, config_from_env, engine_options, normalize_database_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ],
)
def test_normalize_database_url(raw: str, expected: str) -> None:
    assert normalize_database_url(raw) == expected


def test_missing_required_variable_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        DevelopmentConfig()


def test_app_env_defaults_to_production(production_env: pytest.MonkeyPatch) -> None:
    production_env.delenv("APP_ENV")

    config = config_from_env()
    assert isinstance(config, ProductionConfig)
    assert config.DEBUG is False


def test_unknown_app_env_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")

    with pytest.raises(RuntimeError, match="APP_ENV"):
        config_from_env()


def test_production_cookies_are_secure(production_env: pytest.MonkeyPatch) -> None:
    config = config_from_env()
    assert config.JWT_COOKIE_SECURE is True
    assert config.JWT_COOKIE_SAMESITE == "Lax"
    assert config.JWT_COOKIE_CSRF_PROTECT is True


def test_payment_provider_defaults_to_sandbox_and_is_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in {"SECRET_KEY": "x", "JWT_SECRET_KEY": "x" * 32, "DATABASE_URL": "postgresql://u:p@h/db"}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("PAYMENT_PROVIDER", raising=False)

    monkeypatch.delenv("SANDBOX_WEBHOOK_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="SANDBOX_WEBHOOK_SECRET"):  # sandbox needs its signing secret
        DevelopmentConfig()

    monkeypatch.setenv("SANDBOX_WEBHOOK_SECRET", "s" * 32)
    assert DevelopmentConfig().PAYMENT_PROVIDER == "sandbox"

    monkeypatch.setenv("PAYMENT_PROVIDER", "paypal")
    with pytest.raises(RuntimeError, match="PAYMENT_PROVIDER"):
        DevelopmentConfig()


# --- production safety checks (fail fast at startup) -----------------------------------------------


def test_a_safe_production_environment_starts(production_env: pytest.MonkeyPatch) -> None:
    assert ProductionConfig().FRONTEND_URL == "https://kora-outfitters.vercel.app"


@pytest.mark.parametrize(
    ("name", "value", "complaint"),
    [
        ("SECRET_KEY", "short", "SECRET_KEY"),
        ("JWT_SECRET_KEY", "dev-only-jwt-secret-change-me-in-production", "JWT_SECRET_KEY"),  # the .env.example value
        ("SANDBOX_WEBHOOK_SECRET", "x" * 10, "SANDBOX_WEBHOOK_SECRET"),
        ("FRONTEND_URL", "http://kora-outfitters.vercel.app", "FRONTEND_URL"),
        ("DATABASE_URL", NEON_URL.replace("?sslmode=require", ""), "sslmode"),
        ("DATABASE_URL", NEON_URL.replace("sslmode=require", "sslmode=prefer"), "sslmode"),
        ("WEB_CONCURRENCY", "3", "RATELIMIT_STORAGE_URI"),
    ],
)
def test_unsafe_production_settings_refuse_to_start(
    production_env: pytest.MonkeyPatch, name: str, value: str, complaint: str
) -> None:
    production_env.setenv(name, value)
    with pytest.raises(RuntimeError, match=complaint):
        ProductionConfig()


def test_stripe_in_production_needs_both_keys(production_env: pytest.MonkeyPatch) -> None:
    production_env.setenv("PAYMENT_PROVIDER", "stripe")
    production_env.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    production_env.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="STRIPE_WEBHOOK_SECRET"):
        ProductionConfig()


def test_redis_rate_limits_allow_several_workers(production_env: pytest.MonkeyPatch) -> None:
    production_env.setenv("WEB_CONCURRENCY", "3")
    production_env.setenv("RATELIMIT_STORAGE_URI", "redis://red-abc:6379")
    ProductionConfig()  # no error


def test_every_problem_is_reported_at_once(production_env: pytest.MonkeyPatch) -> None:
    production_env.setenv("SECRET_KEY", "x")
    production_env.setenv("FRONTEND_URL", "http://x")
    with pytest.raises(RuntimeError) as error:
        ProductionConfig()
    assert "SECRET_KEY" in str(error.value) and "FRONTEND_URL" in str(error.value)


def test_local_database_does_not_need_ssl(production_env: pytest.MonkeyPatch) -> None:
    production_env.setenv("DATABASE_URL", "postgresql://kora:kora@localhost:5432/kora")
    ProductionConfig()  # e.g. trying a production build on your own machine


# --- connection pool --------------------------------------------------------------------------------


def test_neon_pooler_turns_off_prepared_statements() -> None:
    options = engine_options(normalize_database_url(NEON_URL))
    assert options["pool_pre_ping"] is True
    assert options["connect_args"] == {"connect_timeout": 10, "prepare_threshold": None}


def test_direct_connections_keep_prepared_statements() -> None:
    options = engine_options("postgresql+psycopg://u:p@ep-cool-lab-123456.us-east-1.aws.neon.tech/neondb?sslmode=require")
    assert "prepare_threshold" not in options["connect_args"]
