"""Email verification for accounts: sign-up links, signed tokens, resending, and fixing a wrong address."""

import re
from datetime import timedelta
from typing import Any

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


def sign_up(client: FlaskClient, email: str = SHOPPER_EMAIL) -> dict[str, Any]:
    response = client.post("/api/auth/signup", json={"email": email, "password": PASSWORD, "name": "Maya Chen"})
    assert response.status_code == 201, response.get_json()
    return response.get_json()["user"]


def me(client: FlaskClient) -> dict[str, Any]:
    return client.get("/api/auth/me").get_json()["user"]


def token_from(mailbox: RecordingSender) -> str:
    return TOKEN.search(mailbox.sent[-1].text).group(1)  # type: ignore[union-attr]


def verify(client: FlaskClient, token: str) -> Any:
    return client.post("/api/email/verify", json={"token": token}, headers=csrf_headers(client))


def resend(client: FlaskClient) -> Any:
    return client.post("/api/email/resend-verification", headers=csrf_headers(client))


def change_email(client: FlaskClient, email: str, password: str = PASSWORD) -> Any:
    return client.post("/api/email/change", json={"email": email, "password": password}, headers=csrf_headers(client))


# --- sign-up and the link --------------------------------------------------------------------------


def test_sign_up_logs_in_and_sends_a_verification_link(client: FlaskClient, db_session: Session,
                                                       mailbox: RecordingSender) -> None:
    user = sign_up(client)
    assert user["email_verified"] is False  # can browse and order, but gets no order emails yet
    assert me(client)["email"] == SHOPPER_EMAIL  # already logged in

    [email] = mailbox.sent
    assert email.subject == "Confirm your email for Kora Outfitters"
    assert "http://localhost:3000/verify-email?token=" in email.html

    # signed_in: this browser is logged in as the owner, so the page goes straight to /account.
    assert verify(client, token_from(mailbox)).get_json() == {"verified": True, "email": SHOPPER_EMAIL, "signed_in": True}
    assert me(client)["email_verified"] is True
    assert db_session.get(VerifiedEmail, SHOPPER_EMAIL) is not None


def test_the_link_also_works_logged_out(client: FlaskClient, app: Flask, db_session: Session,
                                        mailbox: RecordingSender) -> None:
    sign_up(client)
    other_device = app.test_client()  # e.g. the email opened on a phone
    result = verify(other_device, token_from(mailbox)).get_json()
    assert result == {"verified": True, "email": SHOPPER_EMAIL, "signed_in": False}  # → the login page
    assert db_session.scalars(select(User)).one().email_verified


def test_failed_sign_up_sends_nothing(client: FlaskClient, app: Flask, db_session: Session,
                                      mailbox: RecordingSender) -> None:
    sign_up(client)
    response = app.test_client().post("/api/auth/signup",
                                      json={"email": SHOPPER_EMAIL, "password": PASSWORD, "name": "Someone"})
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
    assert verify(client, tampered).get_json()["error"]["code"] == "invalid_link"

    # Signed with the right key but for another purpose (different salt): still refused.
    foreign = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="password-reset").dumps({"email": SHOPPER_EMAIL})
    assert verify(client, foreign).get_json()["error"]["code"] == "invalid_link"
    assert db_session.get(VerifiedEmail, SHOPPER_EMAIL) is None


def test_expired_links_are_refused(client: FlaskClient, db_session: Session, mailbox: RecordingSender,
                                   monkeypatch: pytest.MonkeyPatch) -> None:
    sign_up(client)
    monkeypatch.setattr(verification, "MAX_AGE", timedelta(seconds=-1))  # every link is now too old
    response = verify(client, token_from(mailbox))
    assert response.status_code == 410 and response.get_json()["error"]["code"] == "link_expired"


# --- resending ---------------------------------------------------------------------------------------


def test_resend_sends_a_fresh_link(client: FlaskClient, db_session: Session, mailbox: RecordingSender) -> None:
    sign_up(client)
    assert resend(client).get_json() == {"sent": True, "already_verified": False}
    assert len(mailbox.sent) == 2
    verify(client, token_from(mailbox))  # the newest link works
    assert me(client)["email_verified"] is True


def test_resend_is_limited_to_one_a_minute_and_says_when_to_retry(client: FlaskClient, db_session: Session,
                                                                  mailbox: RecordingSender) -> None:
    sign_up(client)
    assert resend(client).status_code == 200
    blocked = resend(client)
    assert blocked.status_code == 429
    # The check-your-email page turns this into its countdown.
    assert 0 < int(blocked.headers["Retry-After"]) <= 60


def test_resend_needs_login(client: FlaskClient, db_session: Session) -> None:
    assert client.post("/api/email/resend-verification").status_code == 401


def test_already_verified_accounts_get_no_new_link(client: FlaskClient, db_session: Session,
                                                   mailbox: RecordingSender) -> None:
    sign_up(client)
    verify(client, token_from(mailbox))
    assert resend(client).get_json() == {"sent": False, "already_verified": True}
    assert len(mailbox.sent) == 1


# --- "wrong email? change it" ----------------------------------------------------------------------------


def test_fixing_a_typo_moves_the_account_and_sends_a_new_link(client: FlaskClient, db_session: Session,
                                                              mailbox: RecordingSender) -> None:
    sign_up(client, "maya@kora-shoppers.dve")  # a typo in the domain
    response = change_email(client, SHOPPER_EMAIL)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["user"]["email"] == SHOPPER_EMAIL

    assert [email.to for email in mailbox.sent] == ["maya@kora-shoppers.dve", SHOPPER_EMAIL]
    assert verify(client, token_from(mailbox)).get_json()["signed_in"] is True  # still logged in, same session
    assert (me(client)["email"], me(client)["email_verified"]) == (SHOPPER_EMAIL, True)


def test_changing_email_needs_the_password(client: FlaskClient, db_session: Session, mailbox: RecordingSender) -> None:
    sign_up(client)
    response = change_email(client, "other@kora-shoppers.dev", password="not-my-password")
    assert response.status_code == 403
    assert me(client)["email"] == SHOPPER_EMAIL


def test_cannot_take_another_accounts_email(client: FlaskClient, app: Flask, db_session: Session,
                                            mailbox: RecordingSender) -> None:
    sign_up(app.test_client(), "taken@kora-shoppers.dev")
    sign_up(client)
    assert change_email(client, "taken@kora-shoppers.dev").status_code == 409


def test_a_confirmed_email_cannot_be_changed_here(client: FlaskClient, db_session: Session,
                                                  mailbox: RecordingSender) -> None:
    sign_up(client)
    verify(client, token_from(mailbox))
    response = change_email(client, "other@kora-shoppers.dev")
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "already_verified"
