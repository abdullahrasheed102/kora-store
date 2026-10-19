"""Payment providers behind one interface. Pick one with PAYMENT_PROVIDER=sandbox|stripe."""

from flask import current_app

from app.payments.base import (
    SESSION_ID_PLACEHOLDER,
    CheckoutRequest,
    CheckoutSession,
    LineItem,
    PaymentEvent,
    PaymentProvider,
)
from app.payments.sandbox_provider import SandboxProvider
from app.payments.stripe_provider import StripeProvider

PROVIDERS: dict[str, type[PaymentProvider]] = {
    StripeProvider.name: StripeProvider,
    SandboxProvider.name: SandboxProvider,
}


def get_provider() -> PaymentProvider:
    """The provider chosen in config. Providers hold no state, so a new instance is cheap."""
    return PROVIDERS[current_app.config["PAYMENT_PROVIDER"]]()


__all__ = [
    "PROVIDERS",
    "SESSION_ID_PLACEHOLDER",
    "CheckoutRequest",
    "CheckoutSession",
    "LineItem",
    "PaymentEvent",
    "PaymentProvider",
    "SandboxProvider",
    "StripeProvider",
    "get_provider",
]
