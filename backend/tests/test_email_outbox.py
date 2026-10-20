"""The email outbox: idempotency, rollback safety, retries, leases, abuse limits, and the providers."""

import json
import smtplib
import threading
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Any

import httpx
import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ProductionConfig, production_problems
from app.mail import outbox
from app.mail.outbox import MAX_ATTEMPTS, RETRY_DELAYS, enqueue, is_blocked, process_outbox, run_scheduled
from app.mail.preview import PREVIEWS, render_preview
from app.mail.render import render
from app.mail.senders import MailpitSender, OutgoingEmail, ResendSender, SendError
from app.models import EmailOutbox, EmailStatus
from tests.conftest import SHOPPER_EMAIL, RecordingSender


def add_email(session: Session, key: str = "test-1", to: str = SHOPPER_EMAIL, **extra: Any) -> int | None:
    """Enqueue a small real template (the caller decides whether to commit)."""
    return enqueue(session, key=key, kind="verify_account", to=to,
                   context={"name": "Maya", "verify_url": "http://localhost:3000/verify-email?token=x"}, **extra)


def rows(session: Session) -> list[EmailOutbox]:
    session.expire_all()
    return list(session.scalars(select(EmailOutbox).order_by(EmailOutbox.id)))


# --- the outbox pattern ---------------------------------------------------------------------------


def test_committed_email_is_sent_right_after_the_commit(db_session: Session, mailbox: RecordingSender) -> None:
    add_email(db_session)
    assert mailbox.sent == []  # nothing leaves before the commit
    db_session.commit()

    assert mailbox.subjects() == ["Confirm your email for Kora Outfitters"]
    [row] = rows(db_session)
    assert (row.status, row.attempts, row.provider_message_id) == (EmailStatus.SENT, 1, "msg_1")
    assert row.sent_at is not None and row.locked_until is None


def test_in_production_the_send_runs_in_a_background_thread(app: Flask, db_session: Session,
                                                           mailbox: RecordingSender) -> None:
    app.config["EMAIL_SEND_IN_BACKGROUND"] = True  # what gunicorn uses: the request doesn't wait
    add_email(db_session)
    db_session.commit()
    for thread in threading.enumerate():
        if thread.name == "outbox-after-commit":
            thread.join(timeout=10)
    assert mailbox.subjects() == ["Confirm your email for Kora Outfitters"]
    assert rows(db_session)[0].status is EmailStatus.SENT


def test_rolled_back_change_sends_no_email(db_session: Session, mailbox: RecordingSender) -> None:
    add_email(db_session)
    db_session.rollback()  # e.g. the order change failed

    assert rows(db_session) == []
    db_session.commit()  # a later, unrelated commit must not send the forgotten email either
    assert mailbox.sent == []


def test_a_failed_commit_takes_the_email_with_it(db_session: Session, mailbox: RecordingSender) -> None:
    from tests.factories import make_order

    order = make_order(db_session)
    add_email(db_session, order_id=order.id)
    order.total_cents = 1  # breaks the "total = subtotal + shipping" CHECK, so the commit fails
    with pytest.raises(Exception):
        db_session.commit()
    db_session.rollback()

    assert rows(db_session) == [] and mailbox.sent == []


def test_the_same_key_twice_is_one_email(db_session: Session, mailbox: RecordingSender) -> None:
    assert add_email(db_session, key="order-confirmation:1") is not None
    assert add_email(db_session, key="order-confirmation:1") is None  # ON CONFLICT DO NOTHING
    db_session.commit()
    assert add_email(db_session, key="order-confirmation:1") is None  # also across transactions
    db_session.commit()

    assert len(rows(db_session)) == 1 and len(mailbox.sent) == 1


def test_the_provider_gets_the_same_idempotency_key(db_session: Session, mailbox: RecordingSender) -> None:
    add_email(db_session, key="order-confirmation:7", reply_to="owner@kora.local")
    db_session.commit()
    [email] = mailbox.sent
    assert email.idempotency_key == "order-confirmation:7"
    assert email.reply_to == "owner@kora.local"
    assert email.sender == "Kora Outfitters <orders@kora.local>"


# --- blocked domains --------------------------------------------------------------------------------


@pytest.mark.parametrize("address", [
    "daniel.brooks@example.com", "a@EXAMPLE.ORG", "a@example.net", "a@mail.example.com",
    "admin@kora.test", "a@shop.test", "a@foo.invalid", "a@localhost", "a@x.example",
])
def test_reserved_domains_are_never_emailed(db_session: Session, mailbox: RecordingSender, address: str) -> None:
    assert is_blocked(address)
    add_email(db_session, to=address)
    db_session.commit()

    [row] = rows(db_session)
    assert (row.status, row.suppressed_reason) == (EmailStatus.SUPPRESSED, "blocked_domain")
    assert mailbox.sent == []


@pytest.mark.parametrize("address", ["a@gmail.com", "a@examples.com", "a@kora.testing.dev", "a@notexample.com"])
def test_lookalike_domains_are_not_blocked(address: str) -> None:
    assert not is_blocked(address)


# --- retries and leases ----------------------------------------------------------------------------


def test_temporary_failures_back_off_then_give_up(db_session: Session, mailbox: RecordingSender) -> None:
    mailbox.fail_with = SendError("Resend 503", retryable=True)
    add_email(db_session)
    db_session.commit()  # attempt 1, right after the commit

    for attempt in range(1, MAX_ATTEMPTS):
        [row] = rows(db_session)
        assert (row.status, row.attempts, row.last_error) == (EmailStatus.PENDING, attempt, "Resend 503")
        wait = row.next_attempt_at - row.last_attempt_at
        assert abs(wait - RETRY_DELAYS[attempt - 1]) < timedelta(seconds=5)
        # Not due yet: a run now leaves it alone.
        assert process_outbox(db_session, now=row.next_attempt_at - timedelta(seconds=1)).retrying == 0
        process_outbox(db_session, now=row.next_attempt_at + timedelta(seconds=1))

    [row] = rows(db_session)
    assert (row.status, row.attempts) == (EmailStatus.FAILED, MAX_ATTEMPTS)
    assert process_outbox(db_session, now=datetime.now(UTC) + timedelta(days=1)).as_dict() == {
        "sent": 0, "retrying": 0, "failed": 0, "suppressed": 0, "deferred": 0}


def test_a_permanent_error_fails_at_once(db_session: Session, mailbox: RecordingSender) -> None:
    mailbox.fail_with = SendError("Resend 422: invalid address", retryable=False)
    add_email(db_session)
    db_session.commit()
    [row] = rows(db_session)
    assert (row.status, row.attempts) == (EmailStatus.FAILED, 1)


def test_an_unexpected_exception_is_retried(db_session: Session, mailbox: RecordingSender) -> None:
    mailbox.fail_with = RuntimeError("bug in a provider library")
    add_email(db_session)
    db_session.commit()  # the error is caught: it must never break the request that caused it
    assert rows(db_session)[0].status is EmailStatus.PENDING


def test_a_crashed_senders_lease_runs_out_and_the_email_is_taken_over(db_session: Session, mailbox: RecordingSender) -> None:
    mailbox.fail_with = SendError("down", retryable=True)
    add_email(db_session)
    db_session.commit()
    [row] = rows(db_session)
    now = datetime.now(UTC)
    # Simulate a sender that claimed the row and then died mid-send.
    row.status, row.locked_until, row.next_attempt_at = EmailStatus.SENDING, now + timedelta(minutes=1), now
    db_session.commit()
    mailbox.fail_with = None

    assert process_outbox(db_session, now=now).sent == 0  # lease still valid: hands off
    assert process_outbox(db_session, now=now + timedelta(minutes=2)).sent == 1  # lease expired
    assert rows(db_session)[0].status is EmailStatus.SENT


# --- abuse limits ------------------------------------------------------------------------------------


def test_one_recipient_gets_at_most_the_daily_cap(app: Flask, db_session: Session, mailbox: RecordingSender) -> None:
    app.config["EMAIL_RECIPIENT_DAILY_CAP"] = 2
    for n in range(3):
        add_email(db_session, key=f"k{n}")
        db_session.commit()

    assert len(mailbox.sent) == 2
    assert [(r.status, r.suppressed_reason) for r in rows(db_session)] == [
        (EmailStatus.SENT, None), (EmailStatus.SENT, None), (EmailStatus.SUPPRESSED, "recipient_daily_cap")]


def test_the_store_owner_is_not_limited_per_recipient(app: Flask, db_session: Session, mailbox: RecordingSender) -> None:
    app.config["EMAIL_RECIPIENT_DAILY_CAP"] = 1
    for n in range(3):
        add_email(db_session, key=f"alert{n}", to="owner@kora.local")
        db_session.commit()
    assert len(mailbox.sent) == 3  # ticket alerts go to our own inbox, not to a stranger


def test_over_the_global_cap_emails_wait_until_tomorrow(app: Flask, db_session: Session, mailbox: RecordingSender) -> None:
    app.config["EMAIL_DAILY_CAP"] = 2
    for n in range(3):
        add_email(db_session, key=f"k{n}", to=f"shopper{n}@kora-shoppers.dev")
        db_session.commit()

    assert len(mailbox.sent) == 2
    waiting = rows(db_session)[2]
    assert waiting.status is EmailStatus.PENDING and waiting.attempts == 0  # postponed, not dropped
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    assert waiting.next_attempt_at == tomorrow

    assert process_outbox(db_session, now=tomorrow + timedelta(minutes=5)).sent == 1  # a new day's budget
    assert len(mailbox.sent) == 3


# --- the scheduled retry job ---------------------------------------------------------------------------


def test_the_retry_job_skips_the_database_when_nothing_can_be_due(db_session: Session, mailbox: RecordingSender) -> None:
    outbox._maybe_due = True  # as after a restart
    assert run_scheduled(db_session)["skipped"] is False  # checks once...
    assert run_scheduled(db_session) == {"skipped": True}  # ...then knows there's nothing to do

    mailbox.fail_with = SendError("down", retryable=True)
    add_email(db_session)
    db_session.commit()  # a new email (here: a failed one) makes the next run look again
    result = run_scheduled(db_session)
    assert result["skipped"] is False and result["waiting"] == 1
    assert run_scheduled(db_session)["skipped"] is False  # a retry is still waiting


def test_the_retry_endpoint_needs_the_secret(client: FlaskClient, db_session: Session) -> None:
    url = "/api/email/outbox/process"
    assert client.post(url).status_code == 401
    assert client.post(url, headers={"Authorization": "Bearer wrong"}).status_code == 401
    response = client.post(url + "?force=1", headers={"Authorization": "Bearer test-outbox-cron-secret"})
    assert response.status_code == 200
    assert response.get_json() == {"skipped": False, "sent": 0, "retrying": 0, "failed": 0, "suppressed": 0,
                                   "deferred": 0, "waiting": 0}


def test_the_retry_endpoint_is_off_without_a_secret(app: Flask, client: FlaskClient) -> None:
    app.config["OUTBOX_CRON_SECRET"] = ""
    assert client.post("/api/email/outbox/process", headers={"Authorization": "Bearer "}).status_code == 404


def test_flask_outbox_process_runs_the_job(app: Flask, db_session: Session, mailbox: RecordingSender) -> None:
    mailbox.fail_with = SendError("down", retryable=True)
    add_email(db_session)
    db_session.commit()
    row = rows(db_session)[0]
    row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)  # make the retry due now
    db_session.commit()
    mailbox.fail_with = None

    result = app.test_cli_runner().invoke(args=["outbox", "process"])
    assert result.exit_code == 0, result.output
    assert "sent: 1" in result.output and len(mailbox.sent) == 1


# --- providers ------------------------------------------------------------------------------------------

EMAIL = OutgoingEmail(to="maya@kora-shoppers.dev", sender="Kora <orders@kora.local>", reply_to="owner@kora.local",
                      subject="Hi", html="<p>Hi</p>", text="Hi", idempotency_key="order-confirmation:1")


def resend_with(handler: Any) -> ResendSender:
    return ResendSender("re_test_key", "https://api.resend.test", transport=httpx.MockTransport(handler))


def test_resend_request_shape() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "re_msg_123"})

    assert resend_with(handler).send(EMAIL) == "re_msg_123"
    request = seen[0]
    assert str(request.url) == "https://api.resend.test/emails"
    assert request.headers["Authorization"] == "Bearer re_test_key"
    assert request.headers["Idempotency-Key"] == "order-confirmation:1"
    assert json.loads(request.content) == {"from": "Kora <orders@kora.local>", "to": ["maya@kora-shoppers.dev"],
                                           "subject": "Hi", "html": "<p>Hi</p>", "text": "Hi", "reply_to": "owner@kora.local"}


@pytest.mark.parametrize(("status", "retryable"), [(429, True), (500, True), (503, True), (409, True),
                                                   (401, False), (403, False), (422, False)])
def test_resend_errors_are_classified(status: int, retryable: bool) -> None:
    sender = resend_with(lambda _request: httpx.Response(status, json={"message": "nope"}))
    with pytest.raises(SendError) as error:
        sender.send(EMAIL)
    assert error.value.retryable is retryable


def test_resend_network_errors_are_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    with pytest.raises(SendError) as error:
        resend_with(handler).send(EMAIL)
    assert error.value.retryable


def test_mailpit_builds_a_multipart_message_with_reply_to(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[EmailMessage] = []

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            assert (host, port) == ("localhost", 1025)

        def __enter__(self) -> "FakeSMTP":
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def send_message(self, message: EmailMessage) -> None:
            sent.append(message)

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    MailpitSender("localhost", 1025).send(EMAIL)
    [message] = sent
    assert message["Reply-To"] == "owner@kora.local"
    assert [part.get_content_type() for part in message.iter_parts()] == ["text/plain", "text/html"]


def test_mailpit_not_running_is_a_retryable_error() -> None:
    with pytest.raises(SendError) as error:
        MailpitSender("127.0.0.1", 1).send(EMAIL)  # nothing listens on port 1
    assert error.value.retryable


# --- templates and config -------------------------------------------------------------------------------


@pytest.mark.parametrize("name", list(PREVIEWS))
def test_every_template_renders(app: Flask, name: str) -> None:
    with app.app_context():
        rendered = render_preview(name)
    assert rendered.subject
    if not name.startswith(("verify", "ticket")):
        assert "KO-1013" in rendered.subject + rendered.text
    assert "None" not in rendered.text  # an empty value printed as "None" is a template bug
    assert rendered.html.startswith("<!doctype html>")


def test_html_escapes_customer_text_and_subjects_stay_on_one_line(app: Flask) -> None:
    with app.app_context():
        rendered = render("ticket_alert", {"audience": "admin", "ticket": {
            "id": 1, "subject": "Help\nBcc: victim@example.com", "name": "<script>alert(1)</script>",
            "email": "a@b.dev", "priority": "high", "source": "agent", "summary": "<b>hi</b>",
            "order_number": None, "admin_url": "http://localhost:3000/admin/tickets"}})
    assert "\n" not in rendered.subject  # a newline can't smuggle in an extra header
    assert "<script>" not in rendered.html and "&lt;script&gt;" in rendered.html
    assert "<b>hi</b>" in rendered.text  # plain text is not HTML: nothing to escape


def test_flask_email_preview_writes_files(app: Flask, tmp_path: Any) -> None:
    result = app.test_cli_runner().invoke(args=["email", "preview", "order_confirmation", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "order_confirmation.html").read_text().startswith("<!doctype html>")
    assert (tmp_path / "order_confirmation.txt").read_text().startswith("Subject: Your order KO-1013 is confirmed")


def production_config(monkeypatch: pytest.MonkeyPatch, **env: str) -> ProductionConfig:
    base = {"APP_ENV": "production", "SECRET_KEY": "s" * 40, "JWT_SECRET_KEY": "j" * 40,
            "SANDBOX_WEBHOOK_SECRET": "w" * 40, "FRONTEND_URL": "https://kora.example.dev",
            "DATABASE_URL": "postgresql://u:p@db.neon.tech/kora?sslmode=require"}
    for name in ("EMAIL_PROVIDER", "RESEND_API_KEY", "EMAIL_FROM", "ADMIN_NOTIFY_EMAIL", "OUTBOX_CRON_SECRET", "TURNSTILE_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    for name, value in (base | env).items():
        monkeypatch.setenv(name, value)
    config = object.__new__(ProductionConfig)
    super(ProductionConfig, config).__init__()  # build it without the fail-fast check
    return config


def test_production_email_settings_are_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    assert production_config(monkeypatch).EMAIL_PROVIDER == "log"  # nothing set: safe default
    problems = production_problems(production_config(monkeypatch, EMAIL_PROVIDER="resend", OUTBOX_CRON_SECRET="short"))
    assert "EMAIL_PROVIDER=resend needs RESEND_API_KEY" in problems
    assert "EMAIL_PROVIDER=resend needs ADMIN_NOTIFY_EMAIL" in problems
    assert any("OUTBOX_CRON_SECRET" in problem for problem in problems)
    assert any("mailpit" in p for p in production_problems(production_config(monkeypatch, EMAIL_PROVIDER="mailpit")))
    ok = production_config(monkeypatch, EMAIL_PROVIDER="resend", RESEND_API_KEY="re_x", ADMIN_NOTIFY_EMAIL="me@x.dev",
                           OUTBOX_CRON_SECRET="c" * 40, TURNSTILE_SECRET_KEY="0x4AAAAAAArealsecret")
    assert production_problems(ok) == []
