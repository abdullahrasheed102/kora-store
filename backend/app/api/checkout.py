"""Checkout and payment providers.

POST /api/checkout/session                    pending order + hosted payment page; returns its URL
POST /api/stripe/webhook                      Stripe events   (when PAYMENT_PROVIDER=stripe)
POST /api/sandbox/webhook                     sandbox events  (when PAYMENT_PROVIDER=sandbox)
GET  /api/sandbox/sessions/<session_id>       the sandbox payment page's data
POST /api/sandbox/sessions/<session_id>/pay   pay with a sandbox test card
"""

from flask import Blueprint, current_app, request
from flask.typing import ResponseReturnValue
from flask_jwt_extended import get_current_user, jwt_required

from app import checkout, payments, sandbox
from app.checkout import CheckoutBody
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
