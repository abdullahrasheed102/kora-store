"""Stripe adapter: real Stripe Checkout (test mode only; live keys are refused in config.py)."""

import json
from collections.abc import Mapping
from typing import Any

import stripe
from flask import current_app

from app.errors import APIError
from app.payments.base import CheckoutRequest, CheckoutSession, PaymentEvent, PaymentProvider


class StripeProvider(PaymentProvider):
    name = "stripe"
    signature_header = "Stripe-Signature"

    def create_checkout_session(self, request: CheckoutRequest) -> CheckoutSession:
        # The idempotency key makes a retried request return the same session, not a second one.
        session_id, url = self._create_session(self._session_params(request), request.idempotency_key)
        return CheckoutSession(id=session_id, url=url)

    def verify_webhook(self, payload: bytes, headers: Mapping[str, str]) -> None:
        # Stripe's library checks the HMAC-SHA256 signature and the 5-minute timestamp window.
        secret = current_app.config["STRIPE_WEBHOOK_SECRET"]
        if not secret:
            raise APIError("payments_not_configured", "Webhook secret is not set.", 503)
        try:
            stripe.Webhook.construct_event(payload, headers.get(self.signature_header), secret)
        except (ValueError, stripe.SignatureVerificationError) as error:
            raise APIError("invalid_signature", "Webhook signature verification failed.", 400) from error

    def parse_event(self, payload: bytes) -> PaymentEvent:
        return json.loads(payload)  # Stripe's events are already in our shape

    def refund_payment(self, payment_id: str, idempotency_key: str, amount_cents: int | None = None) -> None:
        self._create_refund(payment_id, idempotency_key, amount_cents)

    # --- translating our request into Stripe's API ---------------------------------------------

    @staticmethod
    def _session_params(request: CheckoutRequest) -> dict[str, Any]:
        return {
            "mode": "payment",
            # Cards only: they confirm instantly, so "completed" means "paid". (This API version
            # replaced the old `payment_method_types` with this filter on Stripe's dynamic list.)
            "allowed_payment_method_types": ["card"],
            "customer_email": request.email,
            "client_reference_id": request.order_number,
            "metadata": request.metadata,
            "payment_intent_data": {"metadata": request.metadata},  # find the order from a payment
            "line_items": [
                {
                    "quantity": item.quantity,
                    "price_data": {
                        "currency": request.currency,
                        "unit_amount": item.unit_amount_cents,
                        "product_data": {"name": item.name},
                    },
                }
                for item in request.line_items
            ],
            "shipping_options": [
                {
                    "shipping_rate_data": {
                        "type": "fixed_amount",
                        "display_name": request.shipping_name,
                        "fixed_amount": {"amount": request.shipping_cents, "currency": request.currency},
                    }
                }
            ],
            "expires_at": int(request.expires_at.timestamp()),
            "success_url": request.success_url,  # Stripe fills in {CHECKOUT_SESSION_ID} itself
            "cancel_url": request.cancel_url,
        }

    # --- network calls (tests replace these two) -------------------------------------------------

    def _create_session(self, params: dict[str, Any], idempotency_key: str) -> tuple[str, str]:
        session = self._client().v1.checkout.sessions.create(params=params, options={"idempotency_key": idempotency_key})  # type: ignore[arg-type]
        return session.id, str(session.url)

    def _create_refund(self, payment_intent_id: str, idempotency_key: str, amount_cents: int | None) -> None:
        params: dict[str, Any] = {"payment_intent": payment_intent_id, "reason": "requested_by_customer"}
        if amount_cents is not None:
            params["amount"] = amount_cents  # partial refund; without it Stripe refunds everything
        self._client().v1.refunds.create(params=params, options={"idempotency_key": idempotency_key})  # type: ignore[arg-type]

    @staticmethod
    def _client() -> stripe.StripeClient:
        key = current_app.config["STRIPE_SECRET_KEY"]
        if not key:
            raise APIError("payments_not_configured", "Payments are not set up on this server yet.", 503)
        base = current_app.config["STRIPE_API_BASE"]
        return stripe.StripeClient(
            key,
            base_addresses={"api": base} if base else None,
            max_network_retries=2,  # retried requests reuse our idempotency key, so they're safe
        )
