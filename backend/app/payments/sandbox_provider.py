"""Sandbox adapter: our own fake payment provider, so checkout works end to end with no real money.

Built because Stripe doesn't support accounts in Pakistan. It behaves like Stripe where it
matters: a hosted payment page (/pay/sandbox/<session_id> in the frontend), test cards, and
webhooks signed with HMAC-SHA256 plus a timestamp, verified the same way Stripe's are.
"""

import hashlib
import hmac
import json
import logging
import secrets
import time
from collections.abc import Mapping

from flask import current_app

from app.errors import APIError
from app.payments.base import CheckoutRequest, CheckoutSession, PaymentEvent, PaymentProvider

log = logging.getLogger(__name__)

SIGNATURE_TOLERANCE_SECONDS = 300  # same 5-minute window as Stripe


class SandboxProvider(PaymentProvider):
    name = "sandbox"
    signature_header = "Sandbox-Signature"

    def create_checkout_session(self, request: CheckoutRequest) -> CheckoutSession:
        # Nothing to call: the order itself holds everything the payment page shows. The id is
        # long and random because, like Stripe's, it's the buyer's secret for the confirmation page.
        session_id = f"cs_sandbox_{secrets.token_urlsafe(24)}"
        frontend = current_app.config["FRONTEND_URL"].rstrip("/")
        return CheckoutSession(id=session_id, url=f"{frontend}/pay/sandbox/{session_id}")

    def sign(self, payload: bytes, timestamp: int | None = None) -> str:
        """Build the signature header: "t=<unix time>,v1=<hex HMAC-SHA256 of '<t>.<body>'>".

        Signing the timestamp together with the body means neither can be changed on its own,
        so an attacker can't take an old genuine event and stamp it with a new time.
        """
        t = int(time.time()) if timestamp is None else timestamp
        return f"t={t},v1={self._hmac(t, payload)}"

    def verify_webhook(self, payload: bytes, headers: Mapping[str, str]) -> None:
        header = headers.get(self.signature_header) or ""
        parts = dict(part.split("=", 1) for part in header.split(",") if "=" in part)
        try:
            timestamp = int(parts["t"])
            signature = parts["v1"]
        except (KeyError, ValueError):
            raise APIError("invalid_signature", "Webhook signature is missing or malformed.", 400) from None

        if abs(time.time() - timestamp) > SIGNATURE_TOLERANCE_SECONDS:
            raise APIError("invalid_signature", "Webhook timestamp is too old (possible replay).", 400)
        # compare_digest takes the same time whether the first or the last character differs,
        # so response timing can't reveal how much of a forged signature was right.
        if not hmac.compare_digest(self._hmac(timestamp, payload), signature):
            raise APIError("invalid_signature", "Webhook signature verification failed.", 400)

    def parse_event(self, payload: bytes) -> PaymentEvent:
        return json.loads(payload)  # we build sandbox events in Stripe's shape (app/sandbox.py)

    def refund_payment(self, payment_id: str, idempotency_key: str, amount_cents: int | None = None) -> None:
        amount = "in full" if amount_cents is None else f"{amount_cents} cents"
        log.info("Sandbox refund of %s %s (key %s): no real money to return", payment_id, amount, idempotency_key)

    @staticmethod
    def _hmac(timestamp: int, payload: bytes) -> str:
        secret = current_app.config["SANDBOX_WEBHOOK_SECRET"]
        return hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
