"""POST /api/cart/quote: price a cart on the server. No cart is stored; the browser keeps
the list of (variant_id, quantity) and asks for a fresh quote whenever it changes."""

from flask import Blueprint
from flask.typing import ResponseReturnValue
from pydantic import BaseModel, ConfigDict, Field

from app.extensions import db
from app.models import ShippingMethod
from app.pricing import MAX_CART_LINES, MAX_QUANTITY_PER_ITEM, quote_cart
from app.validation import parse_json

bp = Blueprint("cart", __name__)


class CartLine(BaseModel):
    # extra="ignore": if a client sends "price_cents", it is silently dropped, never used.
    model_config = ConfigDict(extra="ignore")
    variant_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=MAX_QUANTITY_PER_ITEM)


class CartQuoteBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    items: list[CartLine] = Field(max_length=MAX_CART_LINES)
    shipping_method: ShippingMethod = ShippingMethod.STANDARD


@bp.post("/cart/quote")
def quote() -> ResponseReturnValue:
    body = parse_json(CartQuoteBody)
    lines = [(line.variant_id, line.quantity) for line in body.items]
    return quote_cart(db.session, lines, body.shipping_method)
