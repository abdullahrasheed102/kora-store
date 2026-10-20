"""Proving an email address is real: signed "confirm your email" links.

The link carries a token signed with SECRET_KEY (itsdangerous, which Flask already depends on).
Nobody can make a valid token without the key, and the signature includes a timestamp, so links
expire. Because the token is self-checking, we don't need a table of issued tokens.

A valid token proves the clicker can read mail at that address. That's all we need to know before
sending order emails there, whether it came from sign-up or from a guest checkout.
"""

from datetime import datetime, timedelta
from typing import Any

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.errors import APIError
from app.models import Order, OrderStatus, User, VerifiedEmail, normalize_email

# The salt keeps these tokens separate from anything else signed with SECRET_KEY: a token made
# for another purpose can never be replayed here.
SALT = "kora-email-verification"
MAX_AGE = timedelta(days=7)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=SALT)


def make_token(email: str, order_id: int | None = None) -> str:
    """`order_id` set: confirming also sends that order's confirmation email."""
    return _serializer().dumps({"email": normalize_email(email), "order_id": order_id})


def verify_url(token: str) -> str:
    return f"{current_app.config['FRONTEND_URL'].rstrip('/')}/verify-email?token={token}"


def read_token(token: str) -> tuple[str, int | None]:
    try:
        data = _serializer().loads(token, max_age=int(MAX_AGE.total_seconds()))
    except SignatureExpired as error:
        raise APIError("link_expired", "This link has expired. Ask for a new one from your account page.", 410) from error
    except BadSignature as error:  # edited, truncated, or made up
        raise APIError("invalid_link", "This link isn't valid. Check you copied all of it.", 400) from error
    return data["email"], data.get("order_id")


def is_verified(session: Session, email: str) -> bool:
    return session.get(VerifiedEmail, normalize_email(email)) is not None


def mark_verified(session: Session, email: str, now: datetime) -> None:
    email = normalize_email(email)
    session.execute(
        insert(VerifiedEmail).values(email=email, verified_at=now).on_conflict_do_nothing(index_elements=["email"])
    )
    # An account with this address is verified too: the same mailbox proved itself.
    session.execute(
        update(User).where(User.email == email, User.email_verified_at.is_(None)).values(email_verified_at=now)
    )


def confirm_email(session: Session, token: str, now: datetime) -> dict[str, Any]:
    """The verification link was clicked. Returns what the confirmation page should say."""
    from app import notifications  # local import: notifications imports this module

    email, order_id = read_token(token)
    mark_verified(session, email, now)

    order_number = None
    if order_id is not None:
        order = session.get(Order, order_id)
        # Check the email matches the order, and the order really went through (a link for a
        # cancelled order shouldn't produce a "thank you for your order" email).
        if order is not None and order.email == email and order.status is not OrderStatus.CANCELLED:
            # Same idempotency key as a direct confirmation: clicking twice sends it once.
            notifications.order_confirmation(session, order)
            order_number = order.order_number
    session.commit()  # the verification and the email row together
    return {"email": email, "order_number": order_number}
