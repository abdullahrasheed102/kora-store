"""Application factory."""

import logging

from flask import Flask, Response, request
from werkzeug.middleware.proxy_fix import ProxyFix

from app import models  # noqa: F401  (registers every table on db.metadata for Alembic)
from app.api import register_blueprints
from app.commands import email_cli, images_cli, orders_cli, outbox_cli, policies_cli
from app.config import BaseConfig, config_from_env
from app.errors import register_error_handlers
from app.extensions import db, jwt, limiter, migrate
from app.seed import seed_command
from app.sessions import register_jwt_callbacks

# Sent with every API response. The API only returns JSON, so the policy can be very strict:
# nothing may load from it as a page, nothing may frame it, and browsers must not guess types.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",  # don't treat JSON as HTML or script
    "X-Frame-Options": "DENY",  # never inside an <iframe> (clickjacking)
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}
# HTTPS only for two years, remembered by the browser. Not in development (plain http://localhost).
HSTS = "max-age=63072000; includeSubDomains"


def create_app(config: BaseConfig | None = None) -> Flask:
    """Build a configured Flask app.

    Pass a config object in tests; otherwise it comes from the environment (APP_ENV).
    """
    app = Flask(__name__, static_folder=None)  # JSON API only; Next.js serves all assets
    app.config.from_object(config or config_from_env())
    if not app.debug and not app.testing:
        # Flask logs only warnings by default; we want our INFO lines (payments, webhooks) in
        # the Render logs too. They go to stderr, which Render collects.
        app.logger.setLevel(logging.INFO)

    if app.config["TRUSTED_PROXY_COUNT"]:
        # Behind Vercel and Render, request.remote_addr is the last proxy's IP. ProxyFix reads
        # the real client IP from X-Forwarded-For, trusting only the proxies we know about.
        # (Trusting more would let a client fake its IP and dodge rate limits.)
        count = app.config["TRUSTED_PROXY_COUNT"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=count, x_proto=count)  # type: ignore[method-assign]

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)
    register_jwt_callbacks(app)

    register_error_handlers(app)
    register_blueprints(app)
    app.cli.add_command(seed_command)
    app.cli.add_command(orders_cli)
    app.cli.add_command(images_cli)
    app.cli.add_command(policies_cli)
    app.cli.add_command(outbox_cli)
    app.cli.add_command(email_cli)

    @app.after_request
    def no_store_for_private_data(response: Response) -> Response:
        # Account data must never be kept by a browser or shared cache.
        if request.path.startswith(("/api/auth", "/api/account", "/api/orders", "/api/checkout", "/api/sandbox", "/api/admin", "/api/email")):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.after_request
    def security_headers(response: Response) -> Response:
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if not app.debug:
            response.headers.setdefault("Strict-Transport-Security", HSTS)
        return response

    return app
