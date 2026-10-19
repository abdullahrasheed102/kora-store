"""GET /api/health: is this instance up, and can it reach the database?"""

from flask import Blueprint, current_app
from flask.typing import ResponseReturnValue
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db

bp = Blueprint("health", __name__)


@bp.get("/health")
def health() -> ResponseReturnValue:
    try:
        # The cheapest possible query: proves we can open a connection and run SQL.
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # Catch only database errors, so a bug in our own code still surfaces as a 500.
        # The full error (with host and user) goes to the logs, never into the response.
        current_app.logger.exception("Health check failed: database unreachable")
        return {"status": "degraded", "database": "unavailable"}, 503
    return {"status": "ok", "database": "ok"}
