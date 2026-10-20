"""Order lookup for guests, and the return rules from the returns policy.

The policy text (policies table, key "returns"):
    "Returns accepted within 30 days of delivery for unworn items with tags attached. US returns
    are free with a prepaid label; international customers pay return shipping. Exchanges for a
    different size or color are free, subject to stock. Final sale (cannot be returned): Crew
    Socks (3-pack) and Gift Cards."

Each sentence becomes a rule below, with one test per rule in tests/test_returns.py. The AI
agent (phase 8) will call the same functions, so the website and the agent always agree.
"""

import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.errors import APIError
from app.models import (
    EventActor,
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    ProductVariant,
    ReturnCreatedBy,
    ReturnRequest,
    ReturnStatus,
    ReturnType,
    User,
    normalize_email,
)

RETURN_WINDOW = timedelta(days=30)
DOMESTIC_COUNTRY = "US"

def order_not_found() -> APIError:
    """The same response for "no such order number" and "wrong email", so nobody can use these
    endpoints to discover which order numbers exist or which email placed an order."""
    return APIError("order_not_found", "We couldn't find an order with that number and email.", 404)

ReturnReason = Literal["doesnt_fit", "changed_mind", "not_as_described", "damaged", "wrong_item", "other"]
REASON_LABELS: dict[str, str] = {
    "doesnt_fit": "Doesn't fit",
    "changed_mind": "Changed my mind",
    "not_as_described": "Not as described",
    "damaged": "Arrived damaged",
    "wrong_item": "Received the wrong item",
    "other": "Other",
}


# --- finding an order -------------------------------------------------------------------------


def normalize_order_number(raw: str) -> str | None:
    """Accept "KO-1005", "ko-1005", " 1005 ". Anything else can't be an order number."""
    text = raw.strip().upper()
    if text.isdigit():
        text = f"KO-{text}"
    return text if re.fullmatch(r"KO-\d{1,10}", text) else None


def find_order(session: Session, order_number: str, email: str | None, user: User | None, *, lock: bool = False) -> Order:
    """Find an order by number + email (guests) or number + account (logged in).

    Number and email are checked in ONE query. Looking up the number first and then comparing
    the email would take a different path (and time) for "wrong email" than for "no such order".
    """
    number = normalize_order_number(order_number)
    if number is None:
        raise order_not_found()
    stmt = select(Order).where(Order.order_number == number)
    if email:
        stmt = stmt.where(Order.email == normalize_email(email))
    elif user is not None:
        stmt = stmt.where(Order.user_id == user.id)
    else:
        raise order_not_found()
    stmt = stmt.options(selectinload(Order.items).selectinload(OrderItem.variant), selectinload(Order.events),
                        selectinload(Order.return_requests))
    if lock:
        stmt = stmt.with_for_update(of=Order)  # creating a return: one at a time per order
    order = session.scalars(stmt).one_or_none()
    if order is None:
        raise order_not_found()
    return order


def tracking_view(order: Order) -> dict[str, Any]:
    """What the public tracking page shows. Deliberately no street address, phone or payment
    details beyond HOW it's paid: knowing an order number and email is not strong proof of
    identity. (The method helps a cash-on-delivery customer have the cash ready.)"""
    return {
        "order_number": order.order_number,
        "status": order.status.value,
        "payment_method": order.payment_method.value,
        "payment_status": order.payment_status.value,
        "total_cents": order.total_cents if order.payment_method is PaymentMethod.COD else None,
        "status_note": order.status_note,
        "created_at": order.created_at.isoformat(),
        "carrier": order.carrier,
        "tracking_number": order.tracking_number,
        "estimated_delivery": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "shipping_city": order.shipping_city,
        "shipping_country": order.shipping_country,
        "items": [
            {"product_name": item.product_name, "size": item.size, "color": item.color, "quantity": item.quantity}
            for item in order.items
        ],
        "events": [
            {"status": event.status.value, "note": event.note, "created_at": event.created_at.isoformat()}
            for event in order.events
        ],
    }


# --- eligibility rules --------------------------------------------------------------------------


@dataclass
class Refusal:
    code: str
    message: str


@dataclass
class ItemEligibility:
    item: OrderItem
    returnable_quantity: int
    refusal: Refusal | None
    exchange_options: list[ProductVariant] = field(default_factory=list)


@dataclass
class Eligibility:
    order: Order
    refusal: Refusal | None  # a reason that applies to the whole order
    deadline: datetime | None
    items: list[ItemEligibility]
    return_shipping: str  # "prepaid_label" or "customer_pays"

    @property
    def eligible(self) -> bool:
        return self.refusal is None and any(item.returnable_quantity > 0 for item in self.items)


def order_refusal(order: Order, now: datetime) -> Refusal | None:
    """Rules 1–4: the whole order must be delivered, not cancelled or returned, and inside the window."""
    if order.status is OrderStatus.CANCELLED:  # rule 2
        return Refusal("order_cancelled", "This order was cancelled, so there's nothing to return.")
    if order.status is OrderStatus.RETURNED:  # rule 3
        return Refusal("already_returned", "This order has already been returned.")
    if order.status is not OrderStatus.DELIVERED or order.delivered_at is None:  # rule 1
        return Refusal("not_delivered", "Returns open once your order is delivered.")
    if now > order.delivered_at + RETURN_WINDOW:  # rule 4 (day 30 itself still counts)
        return Refusal(
            "window_closed",
            f"Returns are accepted within 30 days of delivery. This order was delivered on "
            f"{_long_date(order.delivered_at)}, so the window closed on {_long_date(order.delivered_at + RETURN_WINDOW)}.",
        )
    return None


def _long_date(moment: datetime) -> str:
    return f"{moment:%B} {moment.day}, {moment.year}"  # "September 27, 2026"


def already_requested(order: Order) -> dict[int, int]:
    """order_item_id -> quantity already in a return that wasn't rejected (rule 6)."""
    counts: dict[int, int] = {}
    for request in order.return_requests:
        if request.status is ReturnStatus.REJECTED:
            continue  # a rejected request doesn't use up the quantity
        for line in request.items:
            counts[line["order_item_id"]] = counts.get(line["order_item_id"], 0) + line["quantity"]
    return counts


def item_eligibility(item: OrderItem, requested: int) -> tuple[int, Refusal | None]:
    """Rules 5–6 for one order item: (how many can still be returned, reason if none)."""
    if item.is_final_sale:  # rule 5: uses the snapshot taken at purchase, not today's product
        return 0, Refusal("final_sale", f"{item.product_name} is final sale and can't be returned.")
    remaining = item.quantity - requested
    if remaining <= 0:  # rule 6
        return 0, Refusal("already_requested", "A return for this item has already been requested.")
    return remaining, None


def return_shipping(order: Order) -> str:
    """Rule 8: free prepaid label inside the US; international customers pay return shipping."""
    return "prepaid_label" if order.shipping_country == DOMESTIC_COUNTRY else "customer_pays"


def exchange_options(session: Session, item: OrderItem) -> list[ProductVariant]:
    """Rule 9: other sizes/colours of the same product that are in stock right now."""
    if item.variant is None:
        return []
    return list(
        session.scalars(
            select(ProductVariant)
            .where(
                ProductVariant.product_id == item.variant.product_id,
                ProductVariant.id != item.variant_id,
                ProductVariant.stock > 0,
            )
            .order_by(ProductVariant.id)
        )
    )


def check_eligibility(session: Session, order: Order, now: datetime) -> Eligibility:
    refusal = order_refusal(order, now)
    requested = already_requested(order)
    items = []
    for item in order.items:
        quantity, item_refusal = item_eligibility(item, requested.get(item.id, 0))
        if refusal:  # the order-level reason explains every item
            quantity, item_refusal = 0, refusal
        options = exchange_options(session, item) if quantity > 0 else []
        items.append(ItemEligibility(item, quantity, item_refusal, options))
    deadline = order.delivered_at + RETURN_WINDOW if order.delivered_at else None
    return Eligibility(order, refusal, deadline, items, return_shipping(order))


def days_left(deadline: datetime, now: datetime) -> int:
    """Whole days, rounded UP: 7 days 23 hours is "8 days left", the way people count."""
    return max(math.ceil((deadline - now).total_seconds() / 86400), 0)


def eligibility_view(eligibility: Eligibility, now: datetime) -> dict[str, Any]:
    order = eligibility.order
    deadline = eligibility.deadline
    refusal = eligibility.refusal
    if refusal is None and not eligibility.eligible:
        refusal = Refusal("nothing_returnable", "None of the items in this order can be returned.")
    return {
        "order_number": order.order_number,
        "status": order.status.value,
        "eligible": eligibility.eligible,
        "reason": {"code": refusal.code, "message": refusal.message} if refusal else None,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "return_deadline": deadline.isoformat() if deadline else None,
        "days_left": days_left(deadline, now) if deadline and eligibility.eligible else None,
        "return_shipping": eligibility.return_shipping,
        "items": [
            {
                "order_item_id": entry.item.id,
                "product_name": entry.item.product_name,
                "product_slug": entry.item.variant.product.slug if entry.item.variant else None,
                "size": entry.item.size,
                "color": entry.item.color,
                "quantity": entry.item.quantity,
                "returnable_quantity": entry.returnable_quantity,
                "unit_price_cents": entry.item.unit_price_cents,
                "is_final_sale": entry.item.is_final_sale,
                "reason": {"code": entry.refusal.code, "message": entry.refusal.message} if entry.refusal else None,
                "exchange_options": [
                    {"variant_id": v.id, "size": v.size, "color": v.color} for v in entry.exchange_options
                ],
            }
            for entry in eligibility.items
        ],
        "returns": [return_view(request) for request in order.return_requests],
    }


# --- creating a return --------------------------------------------------------------------------


class ReturnLine(BaseModel):
    order_item_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=10)


class LookupBody(BaseModel):
    order_number: str = Field(min_length=1, max_length=20)
    email: EmailStr | None = Field(None, max_length=254)  # optional when logged in


class CreateReturnBody(LookupBody):
    items: list[ReturnLine] = Field(min_length=1, max_length=20)
    type: ReturnType
    reason: ReturnReason
    comments: str | None = Field(None, max_length=1000)
    exchange_variant_id: int | None = Field(None, ge=1)
    # Rule 7: "unworn items with tags attached". We can't inspect the item online, so the
    # customer confirms it; the warehouse checks when the parcel arrives.
    condition_confirmed: bool

    @model_validator(mode="after")
    def _exchange_shape(self) -> "CreateReturnBody":
        if self.type is ReturnType.EXCHANGE:
            if self.exchange_variant_id is None:
                raise ValueError("choose the size or colour you'd like instead")
            if len(self.items) != 1:
                raise ValueError("exchange one item at a time")
        elif self.exchange_variant_id is not None:
            raise ValueError("exchange_variant_id is only for exchanges")
        return self


def create_return(
    session: Session, body: CreateReturnBody, user: User | None, created_by: ReturnCreatedBy, now: datetime
) -> ReturnRequest:
    # Lock the order: two quick submissions must not both return the same item (rule 6).
    order = find_order(session, body.order_number, body.email, user, lock=True)
    eligibility = check_eligibility(session, order, now)
    if eligibility.refusal:
        raise APIError(eligibility.refusal.code, eligibility.refusal.message, 422)
    if not body.condition_confirmed:  # rule 7
        raise APIError("condition_not_confirmed", "Please confirm the items are unworn with tags attached.", 422)

    by_id = {entry.item.id: entry for entry in eligibility.items}
    lines: list[dict[str, int]] = []
    for line in body.items:
        entry = by_id.get(line.order_item_id)
        if entry is None:
            raise APIError("item_not_in_order", "That item isn't part of this order.", 422)
        if entry.refusal:  # rules 5–6
            raise APIError(entry.refusal.code, entry.refusal.message, 422)
        if line.quantity > entry.returnable_quantity:  # rule 6
            raise APIError(
                "quantity_too_high",
                f"You can return up to {entry.returnable_quantity} of {entry.item.product_name}.",
                422,
            )
        lines.append({"order_item_id": line.order_item_id, "quantity": line.quantity})

    exchange_details = None
    if body.type is ReturnType.EXCHANGE:  # rule 9
        entry = by_id[body.items[0].order_item_id]
        target = next((v for v in entry.exchange_options if v.id == body.exchange_variant_id), None)
        if target is None:
            raise APIError(
                "exchange_unavailable", "That size or colour isn't available for an exchange right now.", 422
            )
        if target.stock < body.items[0].quantity:
            raise APIError("exchange_unavailable", f"Only {target.stock} left in {target.size} / {target.color}.", 422)
        exchange_details = f"Exchange for {target.size} / {target.color} (SKU {target.sku})"

    reason = REASON_LABELS[body.reason] + (f": {body.comments.strip()}" if body.comments and body.comments.strip() else "")
    request = ReturnRequest(
        order=order,
        items=lines,
        reason=reason,
        type=body.type,
        exchange_details=exchange_details,
        status=ReturnStatus.REQUESTED,
        created_by=created_by,
        created_at=now,
    )
    session.add(request)
    names = ", ".join(f"{line['quantity']} × {by_id[line['order_item_id']].item.product_name}" for line in lines)
    # The order's status doesn't change yet (it becomes "returned" once refunded), but the
    # timeline records the request, so support and the AI agent can see it.
    order.events.append(
        OrderEvent(
            status=order.status,
            note=f"{'Exchange' if body.type is ReturnType.EXCHANGE else 'Return'} requested: {names}.",
            created_by=EventActor.AGENT if created_by is ReturnCreatedBy.AGENT else EventActor.SYSTEM,
        )
    )
    session.commit()
    return request


def refund_estimate_cents(request: ReturnRequest) -> int:
    """Items only. Shipping isn't refunded for a normal return (the policy refunds the items)."""
    prices = {item.id: item.unit_price_cents for item in request.order.items}
    return sum(prices[line["order_item_id"]] * line["quantity"] for line in request.items)


def return_view(request: ReturnRequest) -> dict[str, Any]:
    names = {item.id: item for item in request.order.items}
    shipping = return_shipping(request.order)
    return {
        "id": request.id,
        "order_number": request.order.order_number,
        "status": request.status.value,
        "type": request.type.value,
        "reason": request.reason,
        "exchange_details": request.exchange_details,
        "items": [
            {
                "order_item_id": line["order_item_id"],
                "product_name": names[line["order_item_id"]].product_name,
                "size": names[line["order_item_id"]].size,
                "color": names[line["order_item_id"]].color,
                "quantity": line["quantity"],
            }
            for line in request.items
        ],
        "refund_estimate_cents": refund_estimate_cents(request) if request.type is ReturnType.REFUND else 0,
        "return_shipping": shipping,
        "created_at": request.created_at.isoformat(),
    }


def utc_now() -> datetime:
    return datetime.now(UTC)
