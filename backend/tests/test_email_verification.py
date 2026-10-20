"""Email verification: sign-up links, signed tokens, and resending."""

import re
from datetime import timedelta

import pytest
from flask import Flask
from flask.testing import FlaskClient
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mail import verification
from app.models import EmailOutbox, EmailStatus, User, VerifiedEmail
from tests.conftest import SHOPPER_EMAIL, RecordingSender, csrf_headers

TOKEN = re.compile(r"token=([A-Za-z0-9_.\-]+)")
PASSWORD = "a-long-test-password"


def sign_up(client: FlaskClient, email: str = SHOPPER_EMAIL) -> dict:
    response = client.post("/api/auth/signup", json={"email": email, "password": PASSWORD, "name": "Maya Chen"})
    assert response.status_code == 201, response.get_json()
    return response.get_json()["user"]


def token_from(mailbox: RecordingSender) -> str:
    return TOKEN.search(mailbox.sent[-1].text).group(1)  # type: ignore[union-attr]


def test_sign_up_sends_a_verification_link(client: FlaskClient, db_session: Session, mailbox: RecordingSender) -> None:
    user = sign_up(client)
    assert user["email_verified"] is False  # can log in and shop, but gets no order emails yet

    [email] = mailbox.sent
    assert email.subject == "Confirm your email for Kora Outfitters"
    assert "http://localhost:3000/verify-email?token=" in email.html

    response = client.post("/api/email/verify", json={"token": token_from(mailbox)})
    assert response.get_json() == {"verified": True, "email": SHOPPER_EMAIL, "order_number": None}
    assert client.get("/api/auth/me").get_json()["user"]["email_verified"] is True
    assert db_session.get(VerifiedEmail, SHOPPER_EMAIL) is not None


def test_failed_sign_up_sends_nothing(client: FlaskClient, db_session: Session, mailbox: RecordingSender) -> None:
    sign_up(client)
    other = client.application.test_client()
    response = other.post("/api/auth/signup", json={"email": SHOPPER_EMAIL, "password": PASSWORD, "name": "Someone"})
    assert response.status_code == 409
    assert len(mailbox.sent) == 1  # only the first, successful sign-up


def test_sign_up_with_a_reserved_domain_is_never_emailed(client: FlaskClient, db_session: Session,
                                                         mailbox: RecordingSender) -> None:
    sign_up(client, "sam@example.com")
    [row] = db_session.scalars(select(EmailOutbox)).all()
    assert (row.status, row.suppressed_reason) == (EmailStatus.SUPPRESSED, "blocked_domain")
    assert mailbox.sent == []


def test_tampered_or_foreign_tokens_are_rejected(client: FlaskClient, app: Flask, db_session: Session,
                                                 mailbox: RecordingSender) -> None:
    sign_up(client)
    token = token_from(mailbox)
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    assert client.post("/api/email/verify", json={"token": tampered}).get_json()["error"]["code"] == "invalid_link"

    # Signed with the right key but for another purpose (different salt): still refused.
    foreign = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="password-reset").dumps({"email": SHOPPER_EMAIL})
    assert client.post("/api/email/verify", json={"token": foreign}).status_code == 400
    assert db_session.get(VerifiedEmail, SHOPPER_EMAIL) is None


def test_expired_links_are_refused(client: FlaskClient, db_session: Session, mailbox: RecordingSender,
                                   monkeypatch: pytest.MonkeyPatch) -> None:
    sign_up(client)
    monkeypatch.setattr(verification, "MAX_AGE", timedelta(seconds=-1))  # every link is now too old
    response = client.post("/api/email/verify", json={"token": token_from(mailbox)})
    assert response.status_code == 410 and response.get_json()["error"]["code"] == "link_expired"


def test_resend_verification(client: FlaskClient, db_session: Session, mailbox: RecordingSender) -> None:
    sign_up(client)  # also logs in
    response = client.post("/api/email/resend-verification", headers=csrf_headers(client))
    assert response.get_json() == {"sent": True, "already_verified": False}
    assert len(mailbox.sent) == 2

    client.post("/api/email/verify", json={"token": token_from(mailbox)})  # the newest link works
    response = client.post("/api/email/resend-verification", headers=csrf_headers(client))
    assert response.get_json() == {"sent": False, "already_verified": True}


def test_resend_verification_needs_login(client: FlaskClient, db_session: Session) -> None:
    assert client.post("/api/email/resend-verification").status_code == 401


def test_resend_verification_is_rate_limited(client: FlaskClient, db_session: Session, mailbox: RecordingSender) -> None:
    sign_up(client)
    codes = [client.post("/api/email/resend-verification", headers=csrf_headers(client)).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]


def test_confirming_an_order_link_also_verifies_a_matching_account(client: FlaskClient, db_session: Session,
                                                                   mailbox: RecordingSender) -> None:
    sign_up(client)
    token = verification.make_token(SHOPPER_EMAIL, order_id=None)
    client.post("/api/email/verify", json={"token": token})
    user = db_session.scalars(select(User).where(User.email == SHOPPER_EMAIL)).one()
    assert user.email_verified
