"""Extension objects, created unbound and attached to an app in create_app().

Keeping them here (not in app/__init__.py) lets models and routes import `db` without
importing the factory, which avoids circular imports.
"""

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all models (phase 1)."""


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
