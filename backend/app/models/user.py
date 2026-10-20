"""Customer and admin accounts, and their saved addresses."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.extensions import db
from app.models.types import CreatedAt, IntPK, UserRole, enum_column

if TYPE_CHECKING:
    from app.models.order import Order


def normalize_email(email: str) -> str:
    """Emails are compared case-insensitively, so we store them trimmed and lowercase."""
    return email.strip().lower()


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        # Backs up the Python validator: even raw SQL can't insert a mixed-case email.
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    id: Mapped[IntPK]
    email: Mapped[str] = mapped_column(String(254), unique=True)  # 254 = max email length
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[UserRole] = mapped_column(
        enum_column(UserRole, "user_role"),
        default=UserRole.CUSTOMER,
        server_default=UserRole.CUSTOMER.value,
    )
    # Set when the owner clicks the link in the "confirm your email" message. Until then the
    # account works normally, but we send it no order emails (see app/email/verification.py).
    email_verified_at: Mapped[datetime | None]
    created_at: Mapped[CreatedAt]

    addresses: Mapped[list[Address]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="Address.id"
    )
    orders: Mapped[list[Order]] = relationship(back_populates="user")

    @validates("email")
    def _normalize_email(self, _key: str, value: str) -> str:
        return normalize_email(value)

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def is_admin(self) -> bool:
        return self.role is UserRole.ADMIN

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"


class Address(db.Model):
    __tablename__ = "addresses"
    __table_args__ = (
        # A *partial* unique index: only rows where is_default is true are checked,
        # so each user can have many addresses but at most one default.
        Index(
            "uq_addresses_one_default_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[IntPK]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    line1: Mapped[str] = mapped_column(String(200))
    line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))  # not every country has states
    postal_code: Mapped[str] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(2))  # ISO 3166 code: "US", "GB", "CA", "AU"
    is_default: Mapped[bool] = mapped_column(default=False, server_default="false")

    user: Mapped[User] = relationship(back_populates="addresses")
