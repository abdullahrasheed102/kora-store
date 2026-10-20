"""Admin operations: catalog and stock, order status, returns, tickets, policies, and stats.

Every function here assumes the caller is an admin; app/api/admin.py checks that once, for
every route, before any of this runs. Changes to orders and returns write order_events rows
with created_by="admin", so the timeline doubles as an audit trail of who changed what.
"""

import logging
import math
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy import Select, case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app import payments
from app.accounts import order_detail
from app.catalog import escape_like, size_sort_key
from app.errors import APIError
from app.models import (
    EventActor,
    Order,
    OrderEvent,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    Policy,
    Product,
    ProductVariant,
    ReturnRequest,
    ReturnStatus,
    ReturnType,
    SupportTicket,
    TicketPriority,
    TicketStatus,
)
from app.returns import refund_estimate_cents, return_view

log = logging.getLogger(__name__)

PER_PAGE = 20
LOW_STOCK_THRESHOLD = 5
PAID_STATUSES = [s for s in OrderStatus if s not in (OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED)]


def _page(session: Session, stmt: Select[Any], page: int) -> tuple[list[Any], dict[str, int]]:
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = list(session.scalars(stmt.limit(PER_PAGE).offset((page - 1) * PER_PAGE)))
    return rows, {"page": page, "per_page": PER_PAGE, "total": total, "total_pages": math.ceil(total / PER_PAGE)}


def _event(order: Order, note: str, status: OrderStatus | None = None) -> None:
    order.events.append(OrderEvent(status=status or order.status, note=note, created_by=EventActor.ADMIN))


# --- products and stock -------------------------------------------------------------------------


TAG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_TAGS = 10


def clean_tags(tags: list[str] | None) -> list[str] | None:
    """Lowercase, trim and de-duplicate tags, keeping their order. "Autumn Edit" becomes "autumn-edit"."""
    if tags is None:
        return None
    cleaned = list(dict.fromkeys(re.sub(r"[\s_]+", "-", tag.strip().lower()) for tag in tags if tag.strip()))
    for tag in cleaned:
        if len(tag) > 40 or not TAG_PATTERN.match(tag):
            raise ValueError(f"'{tag}' is not a valid tag: use lowercase letters, numbers and hyphens")
    if len(cleaned) > MAX_TAGS:
        raise ValueError(f"at most {MAX_TAGS} tags")
    return cleaned


class ProductFields(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=5000)
    fit_notes: str | None = Field(None, max_length=2000)
    material_care: str | None = Field(None, max_length=2000)
    price_cents: int = Field(ge=0, le=10_000_00)
    is_final_sale: bool = False
    restock_note: str | None = Field(None, max_length=200)
    image_url: HttpUrl | None = None  # only http(s) URLs: no "javascript:" tricks in <img src>
    is_active: bool = True
    tags: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, value: list[str]) -> list[str] | None:
        return clean_tags(value)


class ProductCreate(ProductFields):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)


class ProductUpdate(BaseModel):
    """Every field optional: only what's sent changes (PATCH semantics)."""

    name: str | None = Field(None, min_length=1, max_length=160)
    category: str | None = Field(None, min_length=1, max_length=60)
    description: str | None = Field(None, min_length=1, max_length=5000)
    fit_notes: str | None = Field(None, max_length=2000)
    material_care: str | None = Field(None, max_length=2000)
    price_cents: int | None = Field(None, ge=0, le=10_000_00)
    is_final_sale: bool | None = None
    restock_note: str | None = Field(None, max_length=200)
    image_url: HttpUrl | None = None
    is_active: bool | None = None
    tags: list[str] | None = Field(None, max_length=50)

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, value: list[str] | None) -> list[str] | None:
        return clean_tags(value)


class VariantCreate(BaseModel):
    sku: str = Field(pattern=r"^[A-Z0-9-]{3,40}$")
    size: str = Field(min_length=1, max_length=20)
    color: str = Field(min_length=1, max_length=40)
    stock: int = Field(0, ge=0, le=100_000)
    price_cents: int | None = Field(None, ge=0, le=10_000_00)


class VariantUpdate(BaseModel):
    # A CHANGE, not a new total: "+10 arrived", "-1 damaged". See adjust_stock().
    stock_change: int | None = Field(None, ge=-100_000, le=100_000)
    price_cents: int | None = Field(None, ge=0, le=10_000_00)
    clear_price_override: bool = False


def product_row(product: Product) -> dict[str, Any]:
    stock = sum(v.stock for v in product.variants)
    return {
        "id": product.id,
        "slug": product.slug,
        "name": product.name,
        "category": product.category,
        "price_cents": product.price_cents,
        "is_active": product.is_active,
        "is_final_sale": product.is_final_sale,
        "variant_count": len(product.variants),
        "total_stock": stock,
        "low_stock_variants": sum(1 for v in product.variants if v.stock <= LOW_STOCK_THRESHOLD),
    }


def product_admin_detail(product: Product) -> dict[str, Any]:
    return {
        **product_row(product),
        "description": product.description,
        "fit_notes": product.fit_notes,
        "material_care": product.material_care,
        "restock_note": product.restock_note,
        "image_url": product.image_url,
        "tags": product.tags,
        "variants": [
            {
                "id": v.id,
                "sku": v.sku,
                "size": v.size,
                "color": v.color,
                "stock": v.stock,
                "price_cents": v.price_cents,
                "effective_price_cents": v.effective_price_cents,
            }
            for v in sorted(product.variants, key=lambda v: (v.color, size_sort_key(v.size)))
        ],
    }


def list_products(session: Session, *, q: str | None, active: bool | None, page: int) -> dict[str, Any]:
    stmt = select(Product).options(selectinload(Product.variants)).order_by(Product.category, Product.name, Product.id)
    if q:
        pattern = f"%{escape_like(q)}%"
        stmt = stmt.where(or_(Product.name.ilike(pattern, escape="\\"), Product.slug.ilike(pattern, escape="\\")))
    if active is not None:
        stmt = stmt.where(Product.is_active.is_(active))
    rows, meta = _page(session, stmt, page)
    return {"items": [product_row(p) for p in rows], **meta}


def get_product(session: Session, product_id: int) -> Product:
    product = session.scalars(
        select(Product).where(Product.id == product_id).options(selectinload(Product.variants))
    ).one_or_none()
    if product is None:
        raise APIError("product_not_found", "Product not found.", 404)
    return product


def create_product(session: Session, body: ProductCreate) -> Product:
    data = body.model_dump()
    data["image_url"] = str(body.image_url) if body.image_url else None
    product = Product(**data)
    session.add(product)
    _commit_unique(session, "slug_taken", f"A product with the slug '{body.slug}' already exists.")
    return get_product(session, product.id)


def update_product(session: Session, product_id: int, body: ProductUpdate) -> Product:
    product = get_product(session, product_id)
    for field, value in body.model_dump(exclude_unset=True).items():  # only fields that were sent
        setattr(product, field, str(value) if field == "image_url" and value is not None else value)
    session.commit()
    return get_product(session, product_id)


def add_variant(session: Session, product_id: int, body: VariantCreate) -> Product:
    product = get_product(session, product_id)
    session.add(ProductVariant(product_id=product.id, **body.model_dump()))
    _commit_unique(session, "variant_exists", "That SKU, or that size and colour, already exists.")
    return get_product(session, product_id)


def update_variant(session: Session, variant_id: int, body: VariantUpdate) -> Product:
    variant = session.get(ProductVariant, variant_id)
    if variant is None:
        raise APIError("variant_not_found", "Variant not found.", 404)
    if body.price_cents is not None:
        variant.price_cents = body.price_cents
    if body.clear_price_override:
        variant.price_cents = None
    if body.stock_change:
        adjust_stock(session, variant_id, body.stock_change)
    session.commit()
    return get_product(session, variant.product_id)


def adjust_stock(session: Session, variant_id: int, change: int) -> None:
    """Add or remove stock in ONE atomic SQL statement: SET stock = stock + change.

    Why not "set stock to 30"? The admin typed 30 while looking at a page loaded a minute ago.
    If a customer bought one in between, writing 30 would silently erase that sale (a lost
    update). Postgres applies `stock + change` to the CURRENT value, under a row lock, so the
    admin's change and the sale both count. The WHERE stops stock going below zero.
    """
    result = session.execute(
        update(ProductVariant)
        .where(ProductVariant.id == variant_id, ProductVariant.stock + change >= 0)
        .values(stock=ProductVariant.stock + change)
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise APIError("stock_too_low", "That would make stock negative.", 409)


def _commit_unique(session: Session, code: str, message: str) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise APIError(code, message, 409) from None


# --- orders: a state machine ----------------------------------------------------------------------

# Which status an order may move to next. Anything not listed is refused. "returned" isn't
# here: it's set by refunding returns, so the money and the status can't disagree.
ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING_PAYMENT: {OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED, OrderStatus.PARTIALLY_SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.PARTIALLY_SHIPPED: {OrderStatus.SHIPPED, OrderStatus.DELAYED},
    OrderStatus.SHIPPED: {OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELAYED, OrderStatus.DELIVERED},
    OrderStatus.DELAYED: {OrderStatus.SHIPPED, OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED},
    OrderStatus.OUT_FOR_DELIVERY: {OrderStatus.DELIVERED, OrderStatus.DELAYED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.RETURNED: set(),
}

SHIPPING_STATUSES = {OrderStatus.SHIPPED, OrderStatus.PARTIALLY_SHIPPED}


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    note: str | None = Field(None, max_length=500)
    carrier: str | None = Field(None, max_length=40)
    tracking_number: str | None = Field(None, max_length=64)
    estimated_delivery: date | None = None


def list_orders(session: Session, *, status: OrderStatus | None, q: str | None, page: int) -> dict[str, Any]:
    stmt = select(Order).options(selectinload(Order.items)).order_by(Order.created_at.desc(), Order.id.desc())
    if status:
        stmt = stmt.where(Order.status == status)
    if q:
        pattern = f"%{escape_like(q.strip())}%"
        stmt = stmt.where(
            or_(
                Order.order_number.ilike(pattern, escape="\\"),
                Order.email.ilike(pattern, escape="\\"),
                Order.customer_name.ilike(pattern, escape="\\"),
            )
        )
    rows, meta = _page(session, stmt, page)
    return {
        "items": [
            {
                "order_number": o.order_number,
                "customer_name": o.customer_name,
                "email": o.email,
                "status": o.status.value,
                "payment_method": o.payment_method.value,
                "payment_status": o.payment_status.value,
                "total_cents": o.total_cents,
                "item_count": sum(i.quantity for i in o.items),
                "created_at": o.created_at.isoformat(),
            }
            for o in rows
        ],
        **meta,
    }


def _load_order(session: Session, order_number: str, *, lock: bool = False) -> Order:
    stmt = (
        select(Order)
        .where(Order.order_number == order_number.upper())
        .options(selectinload(Order.items), selectinload(Order.events), selectinload(Order.return_requests))
    )
    if lock:
        stmt = stmt.with_for_update(of=Order)
    order = session.scalars(stmt).one_or_none()
    if order is None:
        raise APIError("order_not_found", "Order not found.", 404)
    return order


def order_admin_detail(order: Order) -> dict[str, Any]:
    return {
        **order_detail(order),
        "user_id": order.user_id,
        "phone": order.phone,
        "can_mark_cash_collected": can_mark_cash_collected(order),
        "payment_id": order.stripe_payment_intent,
        "payment_session_id": order.stripe_session_id,
        "allowed_next_statuses": sorted(s.value for s in ORDER_TRANSITIONS[order.status]),
        "events": [
            {"status": e.status.value, "note": e.note, "created_at": e.created_at.isoformat(), "created_by": e.created_by.value}
            for e in order.events
        ],
    }


def get_order(session: Session, order_number: str) -> dict[str, Any]:
    return order_admin_detail(_load_order(session, order_number))


def change_order_status(session: Session, order_number: str, body: OrderStatusUpdate, now: datetime) -> Order:
    order = _load_order(session, order_number, lock=True)  # one change at a time (webhooks too)
    target = body.status
    if target not in ORDER_TRANSITIONS[order.status]:
        allowed = ", ".join(sorted(s.value for s in ORDER_TRANSITIONS[order.status])) or "none"
        raise APIError(
            "invalid_transition", f"An order can't go from {order.status.value} to {target.value} (allowed: {allowed}).", 409
        )

    if target in SHIPPING_STATUSES:
        carrier, tracking = body.carrier or order.carrier, body.tracking_number or order.tracking_number
        if not carrier or not tracking:
            raise APIError("tracking_required", "Add the carrier and tracking number when shipping.", 400)
        order.carrier, order.tracking_number = carrier, tracking
    if target is OrderStatus.DELAYED and not body.note:
        raise APIError("note_required", "Explain the delay: the customer sees this note.", 400)
    if body.estimated_delivery:
        order.estimated_delivery = body.estimated_delivery
    if target is OrderStatus.DELIVERED:
        order.delivered_at = now  # starts the 30-day return window

    refund_after_commit = False
    if target is OrderStatus.CANCELLED and order.status is OrderStatus.PROCESSING:
        # Stock was already taken (card: when paid; cash on delivery: when placed). Put it back.
        _restock(session, [(item.variant_id, item.quantity) for item in order.items])
        # Card: refund the payment. COD: the courier never collected anything, so nothing to refund.
        refund_after_commit = bool(order.stripe_payment_intent)

    previous = order.status
    order.status = target
    order.status_note = body.note
    _event(order, body.note or f"Status changed from {previous.value} to {target.value}.", target)
    session.commit()

    if refund_after_commit:  # never hold row locks during a network call (same rule as webhooks)
        if _refund(session, order, None, f"refund-cancel-{order.id}"):
            order.payment_status = PaymentStatus.REFUNDED
            session.commit()
    return _load_order(session, order_number)


# Cash is handed to the courier at the door, so it can only be collected once the parcel is there.
CASH_COLLECTABLE_STATUSES = {OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED}


def can_mark_cash_collected(order: Order) -> bool:
    return (
        order.payment_method is PaymentMethod.COD
        and order.payment_status is PaymentStatus.UNPAID
        and order.status in CASH_COLLECTABLE_STATUSES
    )


def mark_cash_collected(session: Session, order_number: str) -> Order:
    """The courier handed over the cash for a cash-on-delivery order."""
    order = _load_order(session, order_number, lock=True)  # two clicks can't both record it
    if order.payment_method is not PaymentMethod.COD:
        raise APIError("not_cash_on_delivery", "Only cash-on-delivery orders are paid in cash.", 409)
    if order.payment_status is not PaymentStatus.UNPAID:
        raise APIError("already_paid", "The cash for this order has already been recorded.", 409)
    if order.status not in CASH_COLLECTABLE_STATUSES:
        raise APIError(
            "not_delivered_yet", "Cash is collected on delivery: mark the order out for delivery or delivered first.", 409
        )
    order.payment_status = PaymentStatus.PAID
    _event(order, f"Cash collected on delivery: {order.total_cents / 100:.2f} USD.")
    session.commit()
    return _load_order(session, order_number)


def _restock(session: Session, lines: list[tuple[int | None, int]]) -> None:
    """Give stock back, locking variants in id order (no deadlocks with checkout webhooks)."""
    totals: dict[int, int] = {}
    for variant_id, quantity in lines:
        if variant_id is not None:
            totals[variant_id] = totals.get(variant_id, 0) + quantity
    for variant_id in sorted(totals):
        adjust_stock(session, variant_id, totals[variant_id])


def _refund(session: Session, order: Order, amount_cents: int | None, key: str) -> bool:
    if not order.stripe_payment_intent:
        return True
    try:
        payments.get_provider().refund_payment(order.stripe_payment_intent, idempotency_key=key, amount_cents=amount_cents)
        return True
    except Exception:
        log.exception("Refund failed for %s", order.order_number)
        _event(order, "Automatic refund failed: needs a manual refund.")
        session.commit()
        return False


# --- returns -----------------------------------------------------------------------------------

RETURN_TRANSITIONS: dict[ReturnStatus, set[ReturnStatus]] = {
    ReturnStatus.REQUESTED: {ReturnStatus.APPROVED, ReturnStatus.REJECTED},
    ReturnStatus.APPROVED: {ReturnStatus.LABEL_SENT, ReturnStatus.RECEIVED, ReturnStatus.REJECTED},
    ReturnStatus.LABEL_SENT: {ReturnStatus.RECEIVED},
    ReturnStatus.RECEIVED: {ReturnStatus.REFUNDED},  # refunds only; an exchange is finished at "received"
    ReturnStatus.REFUNDED: set(),
    ReturnStatus.REJECTED: set(),
}


class ReturnStatusUpdate(BaseModel):
    status: ReturnStatus
    note: str | None = Field(None, max_length=500)


def admin_return_view(request: ReturnRequest) -> dict[str, Any]:
    allowed = RETURN_TRANSITIONS[request.status]
    if request.type is ReturnType.EXCHANGE:
        allowed = allowed - {ReturnStatus.REFUNDED}
    return {
        **return_view(request),
        "customer_name": request.order.customer_name,
        "email": request.order.email,
        "created_by": request.created_by.value,
        "allowed_next_statuses": sorted(s.value for s in allowed),
    }


def list_returns(session: Session, *, status: ReturnStatus | None, page: int) -> dict[str, Any]:
    stmt = (
        select(ReturnRequest)
        .options(selectinload(ReturnRequest.order).selectinload(Order.items))
        .order_by(ReturnRequest.created_at.desc(), ReturnRequest.id.desc())
    )
    if status:
        stmt = stmt.where(ReturnRequest.status == status)
    rows, meta = _page(session, stmt, page)
    return {"items": [admin_return_view(r) for r in rows], **meta}


def change_return_status(session: Session, return_id: int, body: ReturnStatusUpdate) -> ReturnRequest:
    request = session.scalars(
        select(ReturnRequest).where(ReturnRequest.id == return_id).with_for_update()
    ).one_or_none()
    if request is None:
        raise APIError("return_not_found", "Return not found.", 404)
    order = _load_order(session, request.order.order_number, lock=True)
    target = body.status

    allowed = RETURN_TRANSITIONS[request.status]
    if target not in allowed or (target is ReturnStatus.REFUNDED and request.type is ReturnType.EXCHANGE):
        raise APIError("invalid_transition", f"A {request.type.value} can't go from {request.status.value} to {target.value}.", 409)
    if target is ReturnStatus.REJECTED and not body.note:
        raise APIError("note_required", "Tell the customer why the return was rejected.", 400)
    # Every check happens BEFORE anything changes: raising halfway would leave a half-made
    # change in the session for the next commit to save.
    is_cod = order.payment_method is PaymentMethod.COD
    if target is ReturnStatus.REFUNDED and is_cod and order.payment_status is not PaymentStatus.PAID:
        raise APIError("cash_not_collected", "Mark the cash as collected before refunding this order.", 409)

    items = {item.id: item for item in order.items}
    names = ", ".join(f"{line['quantity']} × {items[line['order_item_id']].product_name}" for line in request.items)
    request.status = target

    if target is ReturnStatus.RECEIVED:
        # The items are back in the warehouse: they can be sold again.
        _restock(session, [(items[line["order_item_id"]].variant_id, line["quantity"]) for line in request.items])
        _event(order, body.note or f"Return received at the warehouse: {names}.")
    elif target is ReturnStatus.REFUNDED:
        amount = refund_estimate_cents(request)
        # Card: back to the card automatically. COD: there's no card, so staff pay it by bank
        # transfer or store credit (refunds policy) and this event is the record of it.
        how = "by bank transfer or store credit" if is_cod else "to the original payment method"
        if _all_items_refunded(order, extra=request):
            previous = order.status
            order.status = OrderStatus.RETURNED
            order.payment_status = PaymentStatus.REFUNDED
            order.status_note = f"Returned; refund issued {how}."
            _event(order, body.note or f"Refunded {amount / 100:.2f} USD {how} for {names}. Order fully returned "
                   f"(was {previous.value}).", OrderStatus.RETURNED)
        else:
            _event(order, body.note or f"Refunded {amount / 100:.2f} USD {how} for {names}.")
        session.commit()
        if not is_cod:
            _refund(session, order, amount, f"refund-return-{request.id}")
        return request
    else:
        verb = {ReturnStatus.APPROVED: "approved", ReturnStatus.LABEL_SENT: "label sent", ReturnStatus.REJECTED: "rejected"}
        _event(order, f"Return {verb[target]}: {names}." + (f" {body.note}" if body.note else ""))
    session.commit()
    return request


def _all_items_refunded(order: Order, extra: ReturnRequest) -> bool:
    """True if, counting this refund, every unit in the order has been refunded."""
    refunded: dict[int, int] = {}
    for request in order.return_requests:
        if request.status is ReturnStatus.REFUNDED or request.id == extra.id:
            for line in request.items:
                refunded[line["order_item_id"]] = refunded.get(line["order_item_id"], 0) + line["quantity"]
    return all(refunded.get(item.id, 0) >= item.quantity for item in order.items)


# --- support tickets -----------------------------------------------------------------------------


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    priority: TicketPriority | None = None


def ticket_view(ticket: SupportTicket) -> dict[str, Any]:
    return {
        "id": ticket.id,
        "order_number": ticket.order.order_number if ticket.order else None,
        "email": ticket.email,
        "name": ticket.name,
        "subject": ticket.subject,
        "summary": ticket.summary,
        "priority": ticket.priority.value,
        "status": ticket.status.value,
        "source": ticket.source.value,
        "created_at": ticket.created_at.isoformat(),
    }


PRIORITY_ORDER = {TicketPriority.URGENT: 0, TicketPriority.HIGH: 1, TicketPriority.NORMAL: 2, TicketPriority.LOW: 3}


def list_tickets(session: Session, *, status: TicketStatus | None, page: int) -> dict[str, Any]:
    # Open work first, most urgent first, oldest first within the same priority.
    priority_rank = case({p.value: rank for p, rank in PRIORITY_ORDER.items()}, value=SupportTicket.priority)
    stmt = (
        select(SupportTicket)
        .options(selectinload(SupportTicket.order))
        .order_by((SupportTicket.status == TicketStatus.CLOSED), priority_rank, SupportTicket.created_at)
    )
    if status:
        stmt = stmt.where(SupportTicket.status == status)
    rows, meta = _page(session, stmt, page)
    return {"items": [ticket_view(t) for t in rows], **meta}


def update_ticket(session: Session, ticket_id: int, body: TicketUpdate) -> SupportTicket:
    ticket = session.get(SupportTicket, ticket_id)
    if ticket is None:
        raise APIError("ticket_not_found", "Ticket not found.", 404)
    if body.status:
        ticket.status = body.status
    if body.priority:
        ticket.priority = body.priority
    session.commit()
    return ticket


# --- policies ------------------------------------------------------------------------------------


class PolicyUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=5000)
    summary: str | None = Field(None, max_length=200)  # the one-liner on the homepage; blank clears it

    @field_validator("title", "body")
    @classmethod
    def _strip(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


def update_policy(session: Session, key: str, body: PolicyUpdate) -> Policy:
    policy = session.scalars(select(Policy).where(Policy.key == key)).one_or_none()
    if policy is None:
        raise APIError("policy_not_found", "Policy not found.", 404)
    policy.title, policy.body = body.title, body.body
    policy.summary = body.summary.strip() if body.summary and body.summary.strip() else None
    session.commit()
    return policy


# --- dashboard stats -----------------------------------------------------------------------------

def stats(session: Session, now: datetime) -> dict[str, Any]:
    """Aggregates computed by Postgres (SUM, COUNT, GROUP BY), not by loading rows into Python."""
    paid = Order.status.in_(PAID_STATUSES)

    def revenue_since(days: int) -> tuple[int, int]:
        total, count = session.execute(
            select(func.coalesce(func.sum(Order.total_cents), 0), func.count())
            .where(paid, Order.created_at >= now - timedelta(days=days))
        ).one()
        return int(total), int(count)

    revenue_7, orders_7 = revenue_since(7)
    revenue_30, orders_30 = revenue_since(30)

    day = func.date_trunc("day", Order.created_at).label("day")
    daily = dict(
        session.execute(
            select(day, func.sum(Order.total_cents))
            .where(paid, Order.created_at >= now - timedelta(days=30))
            .group_by(day)
        ).all()
    )
    start = (now - timedelta(days=29)).date()
    by_day = {d.date(): int(total) for d, total in daily.items()}
    daily_revenue = [
        {"date": (start + timedelta(days=i)).isoformat(), "revenue_cents": by_day.get(start + timedelta(days=i), 0)}
        for i in range(30)
    ]

    by_status = dict(session.execute(select(Order.status, func.count()).group_by(Order.status)).all())
    low_stock = session.execute(
        select(ProductVariant.id, ProductVariant.sku, ProductVariant.size, ProductVariant.color, ProductVariant.stock,
               Product.id, Product.name)
        .join(Product)
        .where(Product.is_active, ProductVariant.stock <= LOW_STOCK_THRESHOLD)
        .order_by(ProductVariant.stock, Product.name, ProductVariant.id)
        .limit(10)
    ).all()

    return {
        "revenue_7d_cents": revenue_7,
        "orders_7d": orders_7,
        "revenue_30d_cents": revenue_30,
        "orders_30d": orders_30,
        "average_order_30d_cents": revenue_30 // orders_30 if orders_30 else 0,
        "daily_revenue": daily_revenue,
        "orders_by_status": {status.value: by_status.get(status, 0) for status in OrderStatus},
        "orders_to_ship": by_status.get(OrderStatus.PROCESSING, 0) + by_status.get(OrderStatus.PARTIALLY_SHIPPED, 0),
        "open_returns": session.scalar(
            select(func.count()).select_from(ReturnRequest).where(
                ReturnRequest.status.in_([ReturnStatus.REQUESTED, ReturnStatus.APPROVED, ReturnStatus.LABEL_SENT, ReturnStatus.RECEIVED])
            )
        ) or 0,
        "open_tickets": session.scalar(
            select(func.count()).select_from(SupportTicket).where(SupportTicket.status != TicketStatus.CLOSED)
        ) or 0,
        "low_stock": [
            {"variant_id": v_id, "sku": sku, "size": size, "color": color, "stock": stock, "product_id": p_id, "product_name": name}
            for v_id, sku, size, color, stock, p_id, name in low_stock
        ],
        "low_stock_threshold": LOW_STOCK_THRESHOLD,
    }


def utc_now() -> datetime:
    return datetime.now(UTC)

