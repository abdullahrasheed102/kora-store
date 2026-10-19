"""Health checks.

GET /api/health/live   is the process up? (no database; used by Render's health check)
GET /api/health        is it up AND can it reach the database? (for people and monitoring)
"""

from flask import Blueprint, current_app
from flask.typing import ResponseReturnValue
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db

bp = Blueprint("health", __name__)


@bp.get("/health/live")
def live() -> ResponseReturnValue:
    """Liveness: answers without touching the database.

    Render calls its health check every few seconds. If that ran a query, Neon's compute could
    never go to sleep, and the free plan's monthly compute hours would run out. A process that
    can't reach the database still fails loudly elsewhere: start.sh runs migrations first, and
    /api/health reports it.
    """
    return {"status": "ok"}


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
