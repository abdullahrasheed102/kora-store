"""Application factory."""

from flask import Flask

from app.api import register_blueprints
from app.config import BaseConfig, config_from_env
from app.errors import register_error_handlers
from app.extensions import db, migrate


def create_app(config: BaseConfig | None = None) -> Flask:
    """Build a configured Flask app.

    Pass a config object in tests; otherwise it comes from the environment (APP_ENV).
    """
    app = Flask(__name__, static_folder=None)  # JSON API only; Next.js serves all assets
    app.config.from_object(config or config_from_env())

    db.init_app(app)
    migrate.init_app(app, db)

    register_error_handlers(app)
    register_blueprints(app)

    return app
