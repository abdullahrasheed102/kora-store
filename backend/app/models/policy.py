"""Store policies: the single source of truth for the website and the AI agent."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.types import IntPK, UpdatedAt


class Policy(db.Model):
    __tablename__ = "policies"

    id: Mapped[IntPK]
    key: Mapped[str] = mapped_column(String(60), unique=True)  # "shipping", "returns", ...
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    # One short line for places with no room for the full text, e.g. the homepage perks strip:
    # "Free US shipping on orders over $75".
    summary: Mapped[str | None] = mapped_column(String(200))
    # Which version of backend/seed/policies.json this text came from. `flask policies sync`
    # only overwrites a policy when the file's version is higher, so an admin's edits survive
    # every deploy until someone deliberately ships a new version of that policy.
    seed_version: Mapped[int] = mapped_column(default=1, server_default="1")
    updated_at: Mapped[UpdatedAt]

    def __repr__(self) -> str:
        return f"<Policy {self.key}>"
