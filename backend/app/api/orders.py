"""Orders.

GET /api/account/orders                  the logged-in customer's orders
GET /api/account/orders/<order_number>   one of their orders, with items and timeline

Coming later: order confirmation (phase 4), tracking and returns (phase 5).
"""

from flask import Blueprint, jsonify
from flask.typing import ResponseReturnValue
from flask_jwt_extended import current_user, jwt_required

from app import accounts
from app.extensions import db

bp = Blueprint("orders", __name__)


@bp.get("/account/orders")
@jwt_required()
def list_my_orders() -> ResponseReturnValue:
    return jsonify([accounts.order_summary(order) for order in accounts.list_user_orders(db.session, current_user)])


@bp.get("/account/orders/<order_number>")
@jwt_required()
def get_my_order(order_number: str) -> ResponseReturnValue:
    return accounts.order_detail(accounts.get_user_order(db.session, current_user, order_number))
