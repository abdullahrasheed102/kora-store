"""Extension objects, created unbound and attached to an app in create_app().

Keeping them here (not in app/__init__.py) lets models and routes import `db` without
importing the factory, which avoids circular imports.
"""

from datetime import datetime
from pathlib import Path

from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, registry

# Predictable names for indexes and constraints. Without these, Postgres invents names, and
# Alembic can't reliably find a constraint later to drop or change it.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all models."""

    registry = registry(
        metadata=MetaData(naming_convention=NAMING_CONVENTION),
        # Every `Mapped[datetime]` becomes TIMESTAMPTZ: stored in UTC, never ambiguous.
        type_annotation_map={datetime: DateTime(timezone=True)},
    )


db = SQLAlchemy(model_class=Base)
# Absolute path, so migrations are found no matter which folder a command runs from.
migrate = Migrate(directory=str(Path(__file__).resolve().parent.parent / "migrations"))
jwt = JWTManager()
# Counts requests per client IP by default. Storage comes from RATELIMIT_STORAGE_URI (config.py).
limiter = Limiter(key_func=get_remote_address)
