"""Cloudflare Turnstile: a bot check on guest checkout.

Guests' order emails go out without verifying the address first (app/notifications.py), so we
must stop bots from placing orders with strangers' addresses. Turnstile is Cloudflare's free
CAPTCHA alternative: a widget on the checkout page runs invisible browser checks (and only
rarely asks the person to click) and gives the page a one-time TOKEN. The page sends the token
with the order, and we ask Cloudflare whether it's genuine:

    browser widget ──token──▶ our API ──secret + token──▶ Cloudflare siteverify ──▶ success?

The token proves a real browser passed the check moments ago. It works once and expires after
5 minutes, so a bot can't solve it once and replay it a thousand times.
"""

import logging
from typing import Any

import httpx
from flask import current_app

from app.errors import APIError

log = logging.getLogger(__name__)

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
# The checkout widget is rendered with data-action="checkout". Checking it means a token solved
# on some other page (or another site using our key) can't be used to place orders.
EXPECTED_ACTION = "checkout"
TIMEOUT_SECONDS = 10

# Tests replace this with httpx.MockTransport. None = the real network.
transport: httpx.BaseTransport | None = None


def verify(token: str | None, remote_ip: str | None) -> None:
    """Raise APIError unless Cloudflare confirms the token. Does nothing when switched off."""
    secret = current_app.config["TURNSTILE_SECRET_KEY"]
    if not secret:
        return  # tests and local setups without a key (production refuses to start without one)
    if not token:
        raise APIError("bot_check_required", "Please complete the security check above the order button.", 400)

    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS, transport=transport) as client:
            response = client.post(
                SITEVERIFY_URL,
                data={"secret": secret, "response": token, "remoteip": remote_ip or ""},
            )
            result: dict[str, Any] = response.json()
    except (httpx.HTTPError, ValueError) as error:
        # Fail CLOSED: if we can't ask Cloudflare, we refuse the guest order. Letting it through
        # would switch the protection off exactly when someone found a way to break it.
        log.warning("Turnstile siteverify failed: %s", error)
        raise APIError(
            "bot_check_unavailable", "We couldn't run the security check. Please try again in a moment.", 503
        ) from error

    if not result.get("success"):
        # e.g. "timeout-or-duplicate" (expired or already used) or "invalid-input-response"
        log.info("Turnstile refused a token: %s", result.get("error-codes"))
        raise APIError("bot_check_failed", "The security check didn't pass. Please try it again.", 400)
    action = result.get("action")
    if action and action != EXPECTED_ACTION:  # Cloudflare's test keys return no action
        log.warning("Turnstile token for action %r used at checkout", action)
        raise APIError("bot_check_failed", "The security check didn't pass. Please try it again.", 400)
