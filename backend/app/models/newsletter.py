"""Newsletter sign-ups from the homepage form."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.types import CreatedAt, IntPK


class NewsletterSubscriber(db.Model):
    __tablename__ = "newsletter_subscribers"

    id: Mapped[IntPK]
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lowercase (normalize_email)
    created_at: Mapped[CreatedAt]

    def __repr__(self) -> str:
        return f"<NewsletterSubscriber {self.email}>"
