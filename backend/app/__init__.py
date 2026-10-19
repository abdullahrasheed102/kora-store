"""Application factory."""

from flask import Flask, Response, request
from werkzeug.middleware.proxy_fix import ProxyFix

from app import models  # noqa: F401  (registers every table on db.metadata for Alembic)
from app.api import register_blueprints
from app.config import BaseConfig, config_from_env
from app.errors import register_error_handlers
from app.extensions import db, jwt, limiter, migrate
from app.seed import seed_command
from app.sessions import register_jwt_callbacks


def create_app(config: BaseConfig | None = None) -> Flask:
    """Build a configured Flask app.

    Pass a config object in tests; otherwise it comes from the environment (APP_ENV).
    """
    app = Flask(__name__, static_folder=None)  # JSON API only; Next.js serves all assets
    app.config.from_object(config or config_from_env())

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

    @app.after_request
    def no_store_for_private_data(response: Response) -> Response:
        # Account data must never be kept by a browser or shared cache.
        if request.path.startswith(("/api/auth", "/api/account")):
            response.headers["Cache-Control"] = "no-store"
        return response

    return app
