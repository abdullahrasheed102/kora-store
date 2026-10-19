"""`flask seed [--reset]`: load the demo data in backend/seed/*.json.

The JSON stores dates as "days ago" / "in N days". We turn those into real timestamps at seed
time, relative to *now*, so the demo always looks fresh (an order "delivered 10 days ago" is
always 10 days old, whenever you run the seed).
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import (
    ORDER_NUMBER_START,
    EventActor,
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    Policy,
    Product,
    ProductVariant,
    ReturnCreatedBy,
    ReturnRequest,
    ReturnStatus,
    ReturnType,
    ShippingMethod,
    User,
    UserRole,
)
from app.pricing import shipping_cents
from app.security import hash_password

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
MIN_ADMIN_PASSWORD_LENGTH = 12

# Gaps between timeline steps. They only need to look realistic and keep events in order.
ORDER_PLACED_OFFSET = timedelta(hours=1)  # so "0 days ago" still leaves room for later events
PAYMENT_DELAY = timedelta(minutes=2)
SHIPPING_DELAY = timedelta(days=1)  # policy: orders ship within 1-2 business days
CANCEL_DELAY = timedelta(hours=3)
OUT_FOR_DELIVERY_LEAD = timedelta(hours=4)  # before delivery (or before now)

SHIPPED_STATUSES = {
    OrderStatus.SHIPPED,
    OrderStatus.OUT_FOR_DELIVERY,
    OrderStatus.DELIVERED,
    OrderStatus.DELAYED,
    OrderStatus.RETURNED,
    OrderStatus.PARTIALLY_SHIPPED,
}


@dataclass(frozen=True)
class TimelineEntry:
    status: OrderStatus
    at: datetime
    note: str | None = None


@dataclass(frozen=True)
class SeedCounts:
    policies: int
    products: int
    variants: int
    orders: int
    order_events: int
    return_requests: int
    users: int


def build_order_timeline(
    status: OrderStatus,
    *,
    created_at: datetime,
    now: datetime,
    delivered_at: datetime | None = None,
    carrier: str | None = None,
    status_note: str | None = None,
) -> list[TimelineEntry]:
    """Invent a believable history of events that ends in `status`.

    Every order starts as pending_payment, then processing once paid, the same two events
    the real Stripe webhook will write in phase 4. Then it follows the path for its status.
    """
    paid_at = created_at + PAYMENT_DELAY
    timeline = [TimelineEntry(OrderStatus.PENDING_PAYMENT, created_at)]
    if status is not OrderStatus.PENDING_PAYMENT:  # an unpaid order stops here
        timeline.append(TimelineEntry(OrderStatus.PROCESSING, paid_at))

    if status is OrderStatus.CANCELLED:
        timeline.append(TimelineEntry(OrderStatus.CANCELLED, paid_at + CANCEL_DELAY))
    elif status in SHIPPED_STATUSES:
        shipped_at = created_at + SHIPPING_DELAY
        if status is OrderStatus.PARTIALLY_SHIPPED:
            timeline.append(TimelineEntry(OrderStatus.PARTIALLY_SHIPPED, shipped_at))
        else:
            shipped_note = f"Handed to {carrier}." if carrier else None
            timeline.append(TimelineEntry(OrderStatus.SHIPPED, shipped_at, shipped_note))

        if status is OrderStatus.DELAYED:
            timeline.append(TimelineEntry(OrderStatus.DELAYED, _midpoint(shipped_at, now)))
        elif status is OrderStatus.OUT_FOR_DELIVERY:
            timeline.append(TimelineEntry(OrderStatus.OUT_FOR_DELIVERY, now - OUT_FOR_DELIVERY_LEAD))
        elif status in (OrderStatus.DELIVERED, OrderStatus.RETURNED):
            if delivered_at is None:
                raise ValueError(f"A {status} order needs delivered_days_ago")
            timeline.append(
                TimelineEntry(OrderStatus.OUT_FOR_DELIVERY, delivered_at - OUT_FOR_DELIVERY_LEAD)
            )
            timeline.append(TimelineEntry(OrderStatus.DELIVERED, delivered_at))
            if status is OrderStatus.RETURNED:
                timeline.append(TimelineEntry(OrderStatus.RETURNED, _midpoint(delivered_at, now)))

    # The order's status_note explains its *current* status, so it belongs on the last event.
    if status_note:
        last = timeline[-1]
        timeline[-1] = TimelineEntry(last.status, last.at, status_note)

    _check_timeline(timeline, status, now)
    return timeline


def _midpoint(start: datetime, end: datetime) -> datetime:
    return start + (end - start) / 2


def _check_timeline(timeline: list[TimelineEntry], status: OrderStatus, now: datetime) -> None:
    """Fail loudly on seed data that can't produce a sensible history (e.g. delivered before shipped)."""
    times = [entry.at for entry in timeline]
    if timeline[-1].status is not status:
        raise ValueError(f"No timeline rule for status {status}")
    if times != sorted(times) or len(set(times)) != len(times) or times[-1] > now:
        raise ValueError(f"Seed dates give an impossible {status} timeline: {times}")


def reset_database(session: Session) -> None:
    """Delete every row in every table, and restart all id counters and the order number."""
    tables = ", ".join(f'"{table.name}"' for table in db.metadata.sorted_tables)
    session.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    session.execute(text(f"ALTER SEQUENCE order_number_seq RESTART WITH {ORDER_NUMBER_START}"))
    session.commit()


def seed_database(
    session: Session,
    *,
    now: datetime,
    seed_dir: Path = SEED_DIR,
    admin_email: str | None = None,
    admin_password: str | None = None,
) -> SeedCounts:
    """Load policies, products, orders (with timelines) and the admin user, in one transaction."""
    policies = [Policy(**row) for row in _load_json(seed_dir / "policies.json")]
    session.add_all(policies)

    products = [_build_product(row) for row in _load_json(seed_dir / "products.json")]
    session.add_all(products)
    variants = {
        (product.slug, variant.size, variant.color): variant
        for product in products
        for variant in product.variants
    }

    orders = [_build_order(row, variants, now) for row in _load_json(seed_dir / "orders.json")]
    session.add_all(orders)
    session.flush()  # assigns ids, needed for the return request's order_item_id below

    return_requests = [_build_return_request(order) for order in orders if order.status is OrderStatus.RETURNED]
    session.add_all(return_requests)

    # We inserted KO-1001..KO-1012 by hand, so the counter doesn't know they exist. Move it past
    # the highest one, or the first real checkout would try to reuse KO-1001.
    highest = max(int(order.order_number.removeprefix("KO-")) for order in orders)
    session.execute(select(func.setval("order_number_seq", highest)))

    users = 0
    if admin_email and admin_password:
        session.add(_build_admin(admin_email, admin_password))
        users = 1

    session.commit()
    return SeedCounts(
        policies=len(policies),
        products=len(products),
        variants=len(variants),
        orders=len(orders),
        order_events=sum(len(order.events) for order in orders),
        return_requests=len(return_requests),
        users=users,
    )


def _load_json(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _build_product(row: dict[str, Any]) -> Product:
    variant_rows = row.pop("variants")
    return Product(**row, variants=[ProductVariant(**variant) for variant in variant_rows])


def _build_order(
    row: dict[str, Any],
    variants: dict[tuple[str, str, str], ProductVariant],
    now: datetime,
) -> Order:
    status = OrderStatus(row["status"])
    created_at = now - timedelta(days=row["created_days_ago"]) - ORDER_PLACED_OFFSET
    delivered_at = _days_ago(now, row["delivered_days_ago"])
    eta_days = row["estimated_delivery_in_days"]

    items = [_build_order_item(item, variants) for item in row["items"]]
    subtotal = sum(item.line_total_cents for item in items)
    # Seed orders don't say how they shipped; all are US addresses, so they used standard.
    method = ShippingMethod.STANDARD
    shipping = shipping_cents(method, subtotal)

    address = row["shipping_address"]
    timeline = build_order_timeline(
        status,
        created_at=created_at,
        now=now,
        delivered_at=delivered_at,
        carrier=row["carrier"],
        status_note=row["status_note"],
    )
    return Order(
        order_number=row["order_number"],
        email=row["email"],
        customer_name=row["customer_name"],
        status=status,
        status_note=row["status_note"],
        subtotal_cents=subtotal,
        shipping_cents=shipping,
        total_cents=subtotal + shipping,
        shipping_method=method,
        shipping_line1=address["line1"],
        shipping_line2=address.get("line2"),
        shipping_city=address["city"],
        shipping_state=address.get("state"),
        shipping_postal_code=address["postal_code"],
        shipping_country=address["country"],
        carrier=row["carrier"],
        tracking_number=row["tracking_number"],
        estimated_delivery=(now + timedelta(days=eta_days)).date() if eta_days is not None else None,
        delivered_at=delivered_at,
        created_at=created_at,
        updated_at=timeline[-1].at,
        items=items,
        events=[
            OrderEvent(status=entry.status, note=entry.note, created_at=entry.at, created_by=EventActor.SYSTEM)
            for entry in timeline
        ],
    )


def _build_order_item(
    item: dict[str, Any], variants: dict[tuple[str, str, str], ProductVariant]
) -> OrderItem:
    key = (item["product_slug"], item["size"], item["color"])
    variant = variants.get(key)
    if variant is None:
        raise ValueError(f"Seed order refers to a variant that doesn't exist: {key}")
    product = variant.product
    return OrderItem(
        variant=variant,
        product_name=product.name,
        size=variant.size,
        color=variant.color,
        unit_price_cents=variant.effective_price_cents,
        quantity=item["quantity"],
        is_final_sale=product.is_final_sale,
    )


def _build_return_request(order: Order) -> ReturnRequest:
    """A returned order should have the return that caused it, already refunded."""
    assert order.delivered_at is not None
    return ReturnRequest(
        order=order,
        items=[{"order_item_id": item.id, "quantity": item.quantity} for item in order.items],
        reason="Did not fit.",
        type=ReturnType.REFUND,
        status=ReturnStatus.REFUNDED,
        created_by=ReturnCreatedBy.CUSTOMER,
        created_at=order.delivered_at + timedelta(days=1),
    )


def _build_admin(email: str, password: str) -> User:
    if len(password) < MIN_ADMIN_PASSWORD_LENGTH:
        raise ValueError(f"ADMIN_PASSWORD must be at least {MIN_ADMIN_PASSWORD_LENGTH} characters")
    return User(email=email, password_hash=hash_password(password), name="Store Admin", role=UserRole.ADMIN)


def _days_ago(now: datetime, days: int | None) -> datetime | None:
    return now - timedelta(days=days) if days is not None else None


@click.command("seed")
@click.option("--reset", is_flag=True, help="Delete ALL data (including users) before seeding.")
@with_appcontext
def seed_command(reset: bool) -> None:
    """Load the demo store data from backend/seed/."""
    session = db.session
    if reset:
        reset_database(session)
    elif session.scalar(select(func.count()).select_from(Product)):
        raise click.ClickException("The database already has data. Run `flask seed --reset` to rebuild it.")

    admin_email = current_app.config.get("ADMIN_EMAIL")
    admin_password = current_app.config.get("ADMIN_PASSWORD")
    if not (admin_email and admin_password):
        click.echo("ADMIN_EMAIL / ADMIN_PASSWORD not set: skipping the admin user.", err=True)

    try:
        counts = seed_database(
            session, now=datetime.now(UTC), admin_email=admin_email, admin_password=admin_password
        )
    except ValueError as error:
        session.rollback()
        raise click.ClickException(str(error)) from error

    click.echo(
        f"Seeded {counts.products} products, {counts.variants} variants, {counts.orders} orders "
        f"({counts.order_events} events, {counts.return_requests} return), "
        f"{counts.policies} policies, {counts.users} admin user."
    )
