"""The payment provider interface, and the provider-neutral data that flows through it.

Our checkout code only knows this interface. Each provider is an *adapter*: it translates our
neutral CheckoutRequest into its own API and its webhooks back into one event shape. Adding a
provider means writing one new adapter; checkout, stock and idempotency code never change.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar

# Providers replace this with the real session id in success_url (Stripe's own placeholder).
SESSION_ID_PLACEHOLDER = "{CHECKOUT_SESSION_ID}"

# Events use Stripe's shape for every provider: {"id", "type", "data": {"object": {...}}}.
# Stripe is the industry reference, and it lets one handler (checkout.handle_payment_event) serve all.
PaymentEvent = dict[str, Any]


@dataclass(frozen=True)
class LineItem:
    name: str
    unit_amount_cents: int
    quantity: int


@dataclass(frozen=True)
class CheckoutRequest:
    """Everything a provider needs to show a payment page for one order."""

    order_id: int
    order_number: str
    email: str
    currency: str
    line_items: list[LineItem]
    shipping_name: str
    shipping_cents: int
    total_cents: int
    expires_at: datetime
    success_url: str  # contains SESSION_ID_PLACEHOLDER
    cancel_url: str
    idempotency_key: str

    @property
    def metadata(self) -> dict[str, str]:
        return {"order_id": str(self.order_id), "order_number": self.order_number}


@dataclass(frozen=True)
class CheckoutSession:
    id: str  # also the buyer's secret for the confirmation page
    url: str  # where to send the shopper to pay


class PaymentProvider(ABC):
    name: ClassVar[str]
    signature_header: ClassVar[str]  # HTTP header carrying the webhook signature

    @abstractmethod
    def create_checkout_session(self, request: CheckoutRequest) -> CheckoutSession:
        """Create a hosted payment page for the order."""

    @abstractmethod
    def verify_webhook(self, payload: bytes, headers: Mapping[str, str]) -> None:
        """Raise APIError("invalid_signature", 400) unless the raw body is genuine and recent."""

    @abstractmethod
    def parse_event(self, payload: bytes) -> PaymentEvent:
        """Turn a verified webhook body into a PaymentEvent. Call only after verify_webhook()."""

    @abstractmethod
    def refund_payment(self, payment_id: str, idempotency_key: str, amount_cents: int | None = None) -> None:
        """Refund a payment: in full by default, or `amount_cents` of it (a partial return)."""
