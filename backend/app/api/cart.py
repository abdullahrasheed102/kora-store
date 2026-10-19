"""POST /cart/quote: server-side validation and pricing of a cart (phase 3). No cart is stored."""

from flask import Blueprint

bp = Blueprint("cart", __name__)
