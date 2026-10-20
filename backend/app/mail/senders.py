"""Email providers. Each one takes a finished message and delivers it (or pretends to).

    log      writes the email to the log and sends nothing (tests, and a safe fallback)
    mailpit  SMTP to the local Mailpit container: a fake inbox at http://localhost:8025
    resend   Resend's HTTP API (production). Render's free plan blocks outgoing SMTP ports,
             which is why production uses HTTP instead of SMTP.
"""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Protocol

import httpx
from flask import current_app

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10  # never let a slow provider hold a sender for long; the retry job tries again


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    sender: str  # the From header, e.g. "Kora Outfitters <orders@kora.abdullahrasheed.tech>"
    reply_to: str | None
    subject: str
    html: str
    text: str
    idempotency_key: str


class SendError(Exception):
    """A failed send. `retryable` says whether trying again later could work."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class EmailSender(Protocol):
    name: str

    def send(self, email: OutgoingEmail) -> str:
        """Deliver the email and return the provider's message id. Raise SendError on failure."""
        ...


class LogSender:
    name = "log"

    def send(self, email: OutgoingEmail) -> str:
        log.info("Email (not sent, EMAIL_PROVIDER=log) to=%s subject=%r", email.to, email.subject)
        return f"log-{email.idempotency_key}"


class MailpitSender:
    """Plain SMTP to Mailpit, which catches every message instead of delivering it."""

    name = "mailpit"

    def __init__(self, host: str, port: int) -> None:
        self.host, self.port = host, port

    def send(self, email: OutgoingEmail) -> str:
        message = EmailMessage()
        message["From"] = email.sender
        message["To"] = email.to
        message["Subject"] = email.subject
        if email.reply_to:
            message["Reply-To"] = email.reply_to
        message["Message-ID"] = make_msgid(domain="kora.local")
        # Plain text first, then HTML: mail apps show the LAST part they can display.
        message.set_content(email.text)
        message.add_alternative(email.html, subtype="html")
        try:
            with smtplib.SMTP(self.host, self.port, timeout=TIMEOUT_SECONDS) as smtp:
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as error:
            # Usually "connection refused": Mailpit isn't running (docker compose up -d).
            raise SendError(f"Mailpit at {self.host}:{self.port}: {error}", retryable=True) from error
        return str(message["Message-ID"])


class ResendSender:
    """POST https://api.resend.com/emails (https://resend.com/docs/api-reference/emails/send-email)."""

    name = "resend"

    def __init__(self, api_key: str, base_url: str, transport: httpx.BaseTransport | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.transport = transport  # tests pass httpx.MockTransport; None = the real network

    def send(self, email: OutgoingEmail) -> str:
        payload: dict[str, object] = {
            "from": email.sender,
            "to": [email.to],
            "subject": email.subject,
            "html": email.html,
            "text": email.text,
        }
        if email.reply_to:
            payload["reply_to"] = email.reply_to
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            # Layer 2 of idempotency: if we crash after Resend accepted the email but before we
            # saved "sent", the retry reuses this key and Resend does not deliver a second copy.
            "Idempotency-Key": email.idempotency_key,
        }
        try:
            with httpx.Client(timeout=TIMEOUT_SECONDS, transport=self.transport) as client:
                response = client.post(f"{self.base_url}/emails", json=payload, headers=headers)
        except httpx.HTTPError as error:  # timeout, DNS failure, connection reset...
            raise SendError(f"Resend unreachable: {error}", retryable=True) from error

        if response.status_code in (200, 201):
            return str(response.json().get("id", ""))
        # 429 = rate limited, 409 = the same key is still being processed, 5xx = Resend's problem:
        # all worth retrying. Other 4xx (bad address, unverified domain, bad key) won't fix themselves.
        retryable = response.status_code in (408, 409, 429) or response.status_code >= 500
        raise SendError(f"Resend {response.status_code}: {response.text[:300]}", retryable=retryable)


def get_sender() -> EmailSender:
    """The provider chosen by EMAIL_PROVIDER (validated in config.py)."""
    config = current_app.config
    provider = config["EMAIL_PROVIDER"]
    if provider == "resend":
        return ResendSender(config["RESEND_API_KEY"], config["RESEND_API_URL"])
    if provider == "mailpit":
        return MailpitSender(config["MAILPIT_SMTP_HOST"], config["MAILPIT_SMTP_PORT"])
    return LogSender()
