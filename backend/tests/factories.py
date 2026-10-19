"""Small helpers that build valid rows for tests. Override only the fields a test cares about."""

from typing import Any

from sqlalchemy.orm import Session

from app.models import Order, Product, ProductVariant, ShippingMethod, User
from app.security import hash_password


def make_product(session: Session, **overrides: Any) -> Product:
    fields: dict[str, Any] = {
        "slug": "test-tee",
        "name": "Test Tee",
        "category": "Tops",
        "description": "A tee for tests.",
        "price_cents": 2400,
    }
    product = Product(**(fields | overrides))
    session.add(product)
    session.flush()
    return product


def make_variant(session: Session, product: Product, **overrides: Any) -> ProductVariant:
    fields: dict[str, Any] = {"sku": "TEST-M", "size": "M", "color": "White", "stock": 5}
    variant = ProductVariant(product=product, **(fields | overrides))
    session.add(variant)
    session.flush()
    return variant


def make_user(session: Session, **overrides: Any) -> User:
    fields: dict[str, Any] = {
        "email": "customer@example.com",
        "password_hash": hash_password("a-long-test-password"),
        "name": "Test Customer",
    }
    user = User(**(fields | overrides))
    session.add(user)
    session.flush()
    return user


def make_order(session: Session, **overrides: Any) -> Order:
    fields: dict[str, Any] = {
        "email": "customer@example.com",
        "customer_name": "Test Customer",
        "subtotal_cents": 2400,
        "shipping_cents": 695,
        "total_cents": 3095,
        "shipping_method": ShippingMethod.STANDARD,
        "shipping_line1": "1 Test Street",
        "shipping_city": "Austin",
        "shipping_state": "TX",
        "shipping_postal_code": "78701",
        "shipping_country": "US",
    }
    order = Order(**(fields | overrides))
    session.add(order)
    session.flush()
    return order
