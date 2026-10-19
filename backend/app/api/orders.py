"""Orders.

GET /api/account/orders                                  the logged-in customer's orders
GET /api/account/orders/<order_number>                   one of their orders, with items and timeline
GET  /api/orders/<order_number>/confirmation?session_id=  the thank-you page after checkout
POST /api/orders/track          order number + email -> status and timeline (guests)
POST /api/returns/eligibility   which items can be returned, and why not
POST /api/returns               start a return or exchange
POST /api/support/contact       contact form -> support ticket

Guests prove ownership with order number + email; logged-in customers can leave the email out
for their own orders. Wrong number and wrong email give the same 404.
"""

from flask import Blueprint, Response, jsonify, request
from flask.typing import ResponseReturnValue
from flask_jwt_extended import current_user, get_current_user, jwt_required
from pydantic import BaseModel, EmailStr, Field

from app import accounts, checkout, returns, support
from app.errors import APIError
from app.extensions import db, limiter
from app.models import ReturnCreatedBy
from app.returns import CreateReturnBody, LookupBody
from app.validation import parse_json

bp = Blueprint("orders", __name__)


def _order_number_key() -> str:
    """Rate-limit key per order number: stops someone who knows a number from trying many
    emails against it, even from many IPs."""
    body = request.get_json(silent=True)
    raw = body.get("order_number") if isinstance(body, dict) else None
    number = returns.normalize_order_number(raw) if isinstance(raw, str) else None
    return f"order-lookup:{number or 'invalid'}"


def _was_a_miss(response: Response) -> bool:
    """Only failed lookups use up the budget. The threat is GUESSING (wrong number or email), and
    every wrong guess ends in a 404. A successful lookup reveals nothing new (the caller already
    knew both values), so a real customer tracking, checking and returning is never blocked."""
    return response.status_code == 404


# One budget shared by tracking and returns, so switching endpoints doesn't give more guesses.
lookup_per_ip = limiter.shared_limit(
    "10 per minute; 60 per hour", scope="order-lookup-ip", deduct_when=_was_a_miss
)
lookup_per_order = limiter.shared_limit(
    "20 per hour", scope="order-lookup-number", key_func=_order_number_key, deduct_when=_was_a_miss
)


class TrackBody(LookupBody):
    email: EmailStr = Field(max_length=254)  # tracking always needs the email


@bp.get("/account/orders")
@jwt_required()
def list_my_orders() -> ResponseReturnValue:
    return jsonify([accounts.order_summary(order) for order in accounts.list_user_orders(db.session, current_user)])


@bp.get("/account/orders/<order_number>")
@jwt_required()
def get_my_order(order_number: str) -> ResponseReturnValue:
    return accounts.order_detail(accounts.get_user_order(db.session, current_user, order_number))


@bp.get("/orders/<order_number>/confirmation")
def confirmation(order_number: str) -> ResponseReturnValue:
    session_id = request.args.get("session_id", "")
    if not session_id:
        raise APIError("order_not_found", "Order not found.", 404)
    return accounts.order_detail(checkout.get_confirmation(db.session, order_number, session_id))


@bp.post("/orders/track")
@lookup_per_ip
@lookup_per_order
def track() -> ResponseReturnValue:
    body = parse_json(TrackBody)
    return returns.tracking_view(returns.find_order(db.session, body.order_number, body.email, None))


@bp.post("/returns/eligibility")
@lookup_per_ip
@lookup_per_order
@jwt_required(optional=True)
def return_eligibility() -> ResponseReturnValue:
    body = parse_json(LookupBody)
    order = returns.find_order(db.session, body.order_number, body.email, get_current_user())
    now = returns.utc_now()
    return returns.eligibility_view(returns.check_eligibility(db.session, order, now), now)


@bp.post("/returns")
@lookup_per_ip
@lookup_per_order
@jwt_required(optional=True)  # logged in: CSRF header required, as for every write
def create_return() -> ResponseReturnValue:
    body = parse_json(CreateReturnBody)
    request_ = returns.create_return(db.session, body, get_current_user(), ReturnCreatedBy.CUSTOMER, returns.utc_now())
    return returns.return_view(request_), 201


class ContactBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr = Field(max_length=254)
    order_number: str | None = Field(None, max_length=20)
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=10, max_length=5000)


@bp.post("/support/contact")
@limiter.limit("5 per hour")  # per IP: stops the form being used to flood the support queue
def contact() -> ResponseReturnValue:
    body = parse_json(ContactBody)
    ticket = support.create_ticket(db.session, body.name, body.email, body.subject, body.message, body.order_number)
    return {"id": ticket.id, "status": ticket.status.value}, 201
