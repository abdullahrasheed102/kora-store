"""Stripe Checkout session creation and the Stripe webhook (phase 4)."""

from flask import Blueprint

bp = Blueprint("checkout", __name__)
