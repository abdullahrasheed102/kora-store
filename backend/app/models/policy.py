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
    updated_at: Mapped[UpdatedAt]

    def __repr__(self) -> str:
        return f"<Policy {self.key}>"
