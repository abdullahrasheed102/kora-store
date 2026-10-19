"""Newsletter sign-ups."""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import NewsletterSubscriber, normalize_email


def subscribe(session: Session, email: str) -> None:
    """Add an email to the list. Signing up twice is fine: the second time changes nothing.

    INSERT ... ON CONFLICT DO NOTHING lets the database's UNIQUE constraint decide, so two
    requests racing with the same email can't both insert (a "check first, then insert" could).
    """
    session.execute(
        insert(NewsletterSubscriber)
        .values(email=normalize_email(email))
        .on_conflict_do_nothing(index_elements=["email"])
    )
    session.commit()
