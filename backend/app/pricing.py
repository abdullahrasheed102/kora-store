"""Prices: shipping rules from the shipping policy, and cart quotes.

Used by the seed, /cart/quote and (phase 4) checkout. Keeping the rules in one module means
the cart, checkout and the seed can never disagree about a price.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.catalog import slugify
from app.models import ImageKind, Product, ProductVariant
from app.models.types import ShippingMethod

FREE_SHIPPING_THRESHOLD_CENTS = 7500  # "Free US shipping on orders over $75"

SHIPPING_RATES_CENTS: dict[ShippingMethod, int] = {
    ShippingMethod.STANDARD: 695,
    ShippingMethod.EXPRESS: 1495,
    ShippingMethod.INTERNATIONAL: 1995,
}


def shipping_cents(method: ShippingMethod, subtotal_cents: int) -> int:
    # Only standard shipping is free, and only strictly *over* $75, matching the policy text
    # that customers (and the AI agent) read.
    if method is ShippingMethod.STANDARD and subtotal_cents > FREE_SHIPPING_THRESHOLD_CENTS:
        return 0
    return SHIPPING_RATES_CENTS[method]


# --- Cart quote -----------------------------------------------------------------------------

MAX_QUANTITY_PER_ITEM = 10
MAX_CART_LINES = 50


class CartLine(BaseModel):
    """One line of a cart as the browser sends it: an id and a quantity, nothing else."""

    # extra="ignore": if a client sends "price_cents", it is silently dropped, never used.
    model_config = ConfigDict(extra="ignore")
    variant_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=MAX_QUANTITY_PER_ITEM)


class CartIssue(StrEnum):
    UNAVAILABLE = "unavailable"  # variant doesn't exist, or product was deactivated
    OUT_OF_STOCK = "out_of_stock"
    INSUFFICIENT_STOCK = "insufficient_stock"  # fewer left than requested; quantity reduced


def quote_cart(
    session: Session, lines: list[tuple[int, int]], method: ShippingMethod
) -> dict[str, Any]:
    """Price a cart from the database. The client sends only (variant_id, quantity) pairs.

    Prices, totals and shipping are always calculated here: a browser can be edited by its
    user, so any price it sends would be untrustworthy. Stock is checked too, but this is only
    advice for the shopper; stock is actually taken when payment succeeds (phase 4).
    """
    requested: dict[int, int] = {}  # merge repeated variants, keeping first-seen order
    for variant_id, quantity in lines:
        requested[variant_id] = min(requested.get(variant_id, 0) + quantity, MAX_QUANTITY_PER_ITEM)

    variants = {
        variant.id: variant
        for variant in session.scalars(
            select(ProductVariant)
            .where(ProductVariant.id.in_(requested))
            # One query for the products and one for their photos, not one per line.
            .options(joinedload(ProductVariant.product).selectinload(Product.images))
        )
    }

    items = [_quote_line(variant_id, quantity, variants.get(variant_id)) for variant_id, quantity in requested.items()]
    subtotal = sum(item["line_total_cents"] for item in items)
    shipping = shipping_cents(method, subtotal) if subtotal > 0 else 0
    free_shipping_gap = (
        max(FREE_SHIPPING_THRESHOLD_CENTS + 1 - subtotal, 0) if method is ShippingMethod.STANDARD else None
    )

    return {
        "items": items,
        "item_count": sum(item["quantity"] for item in items),
        "shipping_method": method.value,
        "subtotal_cents": subtotal,
        "shipping_cents": shipping,
        "total_cents": subtotal + shipping,
        "free_shipping_threshold_cents": FREE_SHIPPING_THRESHOLD_CENTS,
        # How much more to add for free standard shipping ("over $75" = at least $75.01).
        "amount_to_free_shipping_cents": free_shipping_gap,
        "has_issues": any(item["issue"] for item in items),
    }


def _quote_line(variant_id: int, requested: int, variant: ProductVariant | None) -> dict[str, Any]:
    if variant is None or not variant.product.is_active:
        return {
            "variant_id": variant_id,
            "requested_quantity": requested,
            "quantity": 0,
            "line_total_cents": 0,
            "issue": CartIssue.UNAVAILABLE.value,
        }

    issue: CartIssue | None = None
    quantity = requested
    if variant.stock == 0:
        issue, quantity = CartIssue.OUT_OF_STOCK, 0
    elif variant.stock < requested:
        issue, quantity = CartIssue.INSUFFICIENT_STOCK, variant.stock

    product = variant.product
    unit_price = variant.effective_price_cents
    return {
        "variant_id": variant.id,
        "sku": variant.sku,
        "product_slug": product.slug,
        "product_name": product.name,
        "category_slug": slugify(product.category),
        "image_url": product.image_url,
        "image": _color_photo(product, variant.color),
        "size": variant.size,
        "color": variant.color,
        "is_final_sale": product.is_final_sale,
        "unit_price_cents": unit_price,
        "requested_quantity": requested,
        "quantity": quantity,
        "available_quantity": min(variant.stock, MAX_QUANTITY_PER_ITEM),
        "line_total_cents": unit_price * quantity,
        "issue": issue.value if issue else None,
    }


def _color_photo(product: Product, color: str) -> dict[str, str] | None:
    """The photo of this exact colour, so the bag shows what the shopper picked."""
    for image in product.images:
        if image.kind is ImageKind.PRODUCT and image.color == color:
            return {"url": image.url, "alt_text": image.alt_text}
    return None
