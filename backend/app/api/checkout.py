"""Checkout and payment providers.

POST /api/checkout/session                    pending order + hosted payment page; returns its URL
POST /api/checkout/cod                        cash on delivery: confirmed order, stock taken now
POST /api/stripe/webhook                      Stripe events   (when PAYMENT_PROVIDER=stripe)
POST /api/sandbox/webhook                     sandbox events  (when PAYMENT_PROVIDER=sandbox)
GET  /api/sandbox/sessions/<session_id>       the sandbox payment page's data
POST /api/sandbox/sessions/<session_id>/pay   pay with a sandbox test card
"""

import re

from flask import Blueprint, current_app, request
from flask.typing import ResponseReturnValue
from flask_jwt_extended import get_current_user, jwt_required

from app import checkout, payments, sandbox
from app.checkout import CheckoutBody, CodCheckoutBody
from app.errors import APIError
from app.extensions import db, limiter
from app.sandbox import SandboxPayBody
from app.validation import parse_json

bp = Blueprint("checkout", __name__)


@bp.post("/checkout/session")
@limiter.limit("10 per minute")
@jwt_required(optional=True)  # guests can check out; if logged in, CSRF is checked as usual
def create_session() -> ResponseReturnValue:
    body = parse_json(CheckoutBody)
    return checkout.create_checkout(db.session, body, get_current_user()), 201


def _cod_phone_key() -> str:
    """Rate-limit key: the phone number's digits. Someone faking orders from many IPs usually
    reuses a few numbers, so this catches what the per-IP limit misses."""
    data = request.get_json(silent=True)
    phone = data.get("phone") if isinstance(data, dict) else None
    return "cod-phone:" + re.sub(r"\D", "", phone if isinstance(phone, str) else "")[:20]


@bp.post("/checkout/cod")
# Stricter than card checkout: a COD order takes stock immediately without any payment, so fake
# orders could block real shoppers from buying. These limits make that slow and noisy.
@limiter.limit("3 per hour; 10 per day")  # per IP
@limiter.limit("3 per day", key_func=_cod_phone_key)  # per phone number
@jwt_required(optional=True)
def create_cod_order() -> ResponseReturnValue:
    body = parse_json(CodCheckoutBody)
    return checkout.create_cod_order(db.session, body, get_current_user()), 201


@bp.post("/stripe/webhook")
def stripe_webhook() -> ResponseReturnValue:
    return _receive_webhook("stripe")


@bp.post("/sandbox/webhook")
def sandbox_webhook() -> ResponseReturnValue:
    return _receive_webhook("sandbox")


def _receive_webhook(provider_name: str) -> ResponseReturnValue:
    provider = payments.get_provider()
    if provider.name != provider_name:
        # Only the active provider's webhook exists. With Stripe live, nobody can post sandbox events.
        raise APIError("not_found", "Not found.", 404)
    # The RAW bytes: the signature covers the exact body, so we must not parse and re-encode it first.
    payload = request.get_data()
    provider.verify_webhook(payload, request.headers)
    event = provider.parse_event(payload)
    outcome = checkout.handle_payment_event(db.session, event)
    current_app.logger.info("%s event %s (%s): %s", provider.name, event["id"], event["type"], outcome)
    # Any 2xx tells the provider "received, don't retry". An exception gives a 500, and it retries.
    return {"received": True, "outcome": outcome}


@bp.get("/sandbox/sessions/<session_id>")
def sandbox_session(session_id: str) -> ResponseReturnValue:
    sandbox.require_sandbox()
    return sandbox.session_view(db.session, session_id)


@bp.post("/sandbox/sessions/<session_id>/pay")
@limiter.limit("10 per minute")
def sandbox_pay(session_id: str) -> ResponseReturnValue:
    sandbox.require_sandbox()
    return sandbox.pay(db.session, session_id, parse_json(SandboxPayBody))
