"""Proving an email address is real: signed "confirm your email" links.

The link carries a token signed with SECRET_KEY (itsdangerous, which Flask already depends on).
Nobody can make a valid token without the key, and the signature includes a timestamp, so links
expire. Because the token is self-checking, we don't need a table of issued tokens.

A valid token proves the clicker can read mail at that address. Only ACCOUNTS verify their email:
guests get their order emails directly (see app/notifications.py for why, and what limits abuse).
"""

from datetime import datetime, timedelta

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.errors import APIError
from app.models import User, VerifiedEmail, normalize_email

# The salt keeps these tokens separate from anything else signed with SECRET_KEY: a token made
# for another purpose can never be replayed here.
SALT = "kora-email-verification"
MAX_AGE = timedelta(days=7)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=SALT)


def make_token(email: str) -> str:
    return _serializer().dumps({"email": normalize_email(email)})


def verify_url(token: str) -> str:
    return f"{current_app.config['FRONTEND_URL'].rstrip('/')}/verify-email?token={token}"


def read_token(token: str) -> str:
    try:
        data = _serializer().loads(token, max_age=int(MAX_AGE.total_seconds()))
    except SignatureExpired as error:
        raise APIError("link_expired", "This link has expired. Ask for a new one from your account page.", 410) from error
    except BadSignature as error:  # edited, truncated, or made up
        raise APIError("invalid_link", "This link isn't valid. Check you copied all of it.", 400) from error
    return str(data["email"])


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


def confirm_email(session: Session, token: str, now: datetime) -> str:
    """The verification link was clicked. Returns the address that is now verified."""
    email = read_token(token)
    mark_verified(session, email, now)
    session.commit()
    return email
