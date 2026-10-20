"""Admin API. Every route here requires a logged-in user with role "admin".

GET   /api/admin/stats                           dashboard numbers
GET   /api/admin/products  · POST                list / create products
GET   /api/admin/products/<id> · PATCH           one product / edit (incl. deactivate)
POST  /api/admin/products/<id>/variants          add a size/colour
PATCH /api/admin/variants/<id>                   adjust stock (+/-), price override
GET   /api/admin/orders                          list with status filter and search
GET   /api/admin/orders/<number>                 full detail + allowed next statuses
POST  /api/admin/orders/<number>/status          move along the state machine (writes an event)
POST  /api/admin/orders/<number>/cash-collected  cash on delivery: the courier handed over the cash
GET   /api/admin/returns                         list with status filter
POST  /api/admin/returns/<id>/status             approve / reject / received / refunded
GET   /api/admin/tickets · PATCH /<id>           support tickets
PUT   /api/admin/policies/<key>                  edit policy text
"""

from flask import Blueprint, request
from flask.typing import ResponseReturnValue
from flask_jwt_extended import get_current_user, verify_jwt_in_request
from pydantic import BaseModel, Field

from app import admin
from app.admin import (
    OrderStatusUpdate,
    PolicyUpdate,
    ProductCreate,
    ProductUpdate,
    ReturnStatusUpdate,
    TicketUpdate,
    VariantCreate,
    VariantUpdate,
)
from app.catalog import policy_dict
from app.errors import APIError
from app.extensions import db
from app.models import OrderStatus, ReturnStatus, TicketStatus
from app.validation import parse_json, parse_query

bp = Blueprint("admin", __name__)


@bp.before_request
def require_admin() -> None:
    """Runs before EVERY route in this blueprint, so no admin route can forget the check.

    Authentication (who are you?) → verify_jwt_in_request: no valid cookie gives 401, and for
    POST/PUT/PATCH/DELETE a missing CSRF header gives 403.
    Authorization (may you do this?) → the role, read fresh from the database on every request,
    so removing someone's admin role takes effect immediately.
    """
    verify_jwt_in_request()
    user = get_current_user()
    if user is None or not user.is_admin:
        raise APIError("forbidden", "You don't have permission to do that.", 403)


class ListQuery(BaseModel):
    q: str | None = Field(None, max_length=100)
    page: int = Field(1, ge=1)


class ProductListQuery(ListQuery):
    active: bool | None = None


class OrderListQuery(ListQuery):
    status: OrderStatus | None = None


class ReturnListQuery(ListQuery):
    status: ReturnStatus | None = None


class TicketListQuery(ListQuery):
    status: TicketStatus | None = None


# --- dashboard -------------------------------------------------------------------------------------


@bp.get("/admin/stats")
def stats() -> ResponseReturnValue:
    return admin.stats(db.session, admin.utc_now())


# --- products ----------------------------------------------------------------------------------------


@bp.get("/admin/products")
def list_products() -> ResponseReturnValue:
    query = parse_query(ProductListQuery, request.args)
    return admin.list_products(db.session, q=query.q, active=query.active, page=query.page)


@bp.post("/admin/products")
def create_product() -> ResponseReturnValue:
    product = admin.create_product(db.session, parse_json(ProductCreate))
    return admin.product_admin_detail(product), 201


@bp.get("/admin/products/<int:product_id>")
def get_product(product_id: int) -> ResponseReturnValue:
    return admin.product_admin_detail(admin.get_product(db.session, product_id))


@bp.patch("/admin/products/<int:product_id>")
def update_product(product_id: int) -> ResponseReturnValue:
    return admin.product_admin_detail(admin.update_product(db.session, product_id, parse_json(ProductUpdate)))


@bp.post("/admin/products/<int:product_id>/variants")
def add_variant(product_id: int) -> ResponseReturnValue:
    return admin.product_admin_detail(admin.add_variant(db.session, product_id, parse_json(VariantCreate))), 201


@bp.patch("/admin/variants/<int:variant_id>")
def update_variant(variant_id: int) -> ResponseReturnValue:
    return admin.product_admin_detail(admin.update_variant(db.session, variant_id, parse_json(VariantUpdate)))


# --- orders ------------------------------------------------------------------------------------------


@bp.get("/admin/orders")
def list_orders() -> ResponseReturnValue:
    query = parse_query(OrderListQuery, request.args)
    return admin.list_orders(db.session, status=query.status, q=query.q, page=query.page)


@bp.get("/admin/orders/<order_number>")
def get_order(order_number: str) -> ResponseReturnValue:
    return admin.get_order(db.session, order_number)


@bp.post("/admin/orders/<order_number>/status")
def change_order_status(order_number: str) -> ResponseReturnValue:
    order = admin.change_order_status(db.session, order_number, parse_json(OrderStatusUpdate), admin.utc_now())
    return admin.order_admin_detail(order)


@bp.post("/admin/orders/<order_number>/cash-collected")
def mark_cash_collected(order_number: str) -> ResponseReturnValue:
    order = admin.mark_cash_collected(db.session, order_number)
    return admin.order_admin_detail(order)


# --- returns -----------------------------------------------------------------------------------------


@bp.get("/admin/returns")
def list_returns() -> ResponseReturnValue:
    query = parse_query(ReturnListQuery, request.args)
    return admin.list_returns(db.session, status=query.status, page=query.page)


@bp.post("/admin/returns/<int:return_id>/status")
def change_return_status(return_id: int) -> ResponseReturnValue:
    return admin.admin_return_view(admin.change_return_status(db.session, return_id, parse_json(ReturnStatusUpdate)))


# --- tickets and policies ------------------------------------------------------------------------------


@bp.get("/admin/tickets")
def list_tickets() -> ResponseReturnValue:
    query = parse_query(TicketListQuery, request.args)
    return admin.list_tickets(db.session, status=query.status, page=query.page)


@bp.patch("/admin/tickets/<int:ticket_id>")
def update_ticket(ticket_id: int) -> ResponseReturnValue:
    return admin.ticket_view(admin.update_ticket(db.session, ticket_id, parse_json(TicketUpdate)))


@bp.put("/admin/policies/<key>")
def update_policy(key: str) -> ResponseReturnValue:
    return policy_dict(admin.update_policy(db.session, key, parse_json(PolicyUpdate)))

