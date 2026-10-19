"""Shipping rules from the shipping policy."""

import pytest

from app.models import ShippingMethod
from app.pricing import shipping_cents


@pytest.mark.parametrize(
    ("method", "subtotal", "expected"),
    [
        (ShippingMethod.STANDARD, 7499, 695),
        (ShippingMethod.STANDARD, 7500, 695),  # exactly $75 is not "over $75"
        (ShippingMethod.STANDARD, 7501, 0),
        (ShippingMethod.EXPRESS, 20000, 1495),  # express is never free
        (ShippingMethod.INTERNATIONAL, 20000, 1995),
    ],
)
def test_shipping_cents(method: ShippingMethod, subtotal: int, expected: int) -> None:
    assert shipping_cents(method, subtotal) == expected
