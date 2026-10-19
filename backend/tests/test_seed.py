"""The seed command: counts, relative dates, totals, timelines and the admin user."""

from datetime import timedelta

import pytest
from flask import Flask
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Order,
    OrderStatus,
    Policy,
    Product,
    ProductVariant,
    ReturnRequest,
    ReturnStatus,
    User,
    UserRole,
)
from app.pricing import shipping_cents
from app.security import verify_password
from app.seed import SeedCounts, build_order_timeline, reset_database, seed_database
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, FIXED_NOW
from tests.factories import make_order


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def get_order(session: Session, number: str) -> Order:
    return session.scalars(select(Order).where(Order.order_number == number)).one()


def test_seed_loads_the_expected_counts(db_session: Session, seeded: SeedCounts) -> None:
    # Phase 1 "done when": 20 products, 217 variants, 12 orders and 5 policies.
    assert count(db_session, Product) == 20
    assert count(db_session, ProductVariant) == 217
    assert count(db_session, Order) == 12
    assert count(db_session, Policy) == 5
    assert count(db_session, ReturnRequest) == 1
    assert seeded.order_events == 47


def test_relative_days_become_real_dates(db_session: Session, seeded: SeedCounts) -> None:
    ko_1007 = get_order(db_session, "KO-1007")  # delivered_days_ago: 49
    assert ko_1007.delivered_at == FIXED_NOW - timedelta(days=49)

    ko_1002 = get_order(db_session, "KO-1002")  # estimated_delivery_in_days: 2
    assert ko_1002.estimated_delivery == (FIXED_NOW + timedelta(days=2)).date()


def test_totals_are_calculated_from_catalog_prices(db_session: Session, seeded: SeedCounts) -> None:
    ko_1001 = get_order(db_session, "KO-1001")  # 2 tees at $24 + jeans at $79
    assert ko_1001.subtotal_cents == 2 * 2400 + 7900

    for order in db_session.scalars(select(Order)):
        assert order.subtotal_cents == sum(item.line_total_cents for item in order.items)
        assert order.shipping_cents == shipping_cents(order.shipping_method, order.subtotal_cents)
        assert order.total_cents == order.subtotal_cents + order.shipping_cents


def test_final_sale_is_snapshotted_on_order_items(db_session: Session, seeded: SeedCounts) -> None:
    ko_1011 = get_order(db_session, "KO-1011")  # contains the crew socks (final sale)
    final_sale = {item.product_name: item.is_final_sale for item in ko_1011.items}
    assert final_sale["Crew Socks (3-pack)"] is True
    assert False in final_sale.values()


def test_every_timeline_is_ordered_and_ends_in_the_order_status(db_session: Session, seeded: SeedCounts) -> None:
    for order in db_session.scalars(select(Order)):
        times = [event.created_at for event in order.events]
        assert order.events[0].status is OrderStatus.PENDING_PAYMENT, order.order_number
        assert order.events[-1].status is order.status, order.order_number
        assert times == sorted(times), order.order_number
        assert times[-1] <= FIXED_NOW, order.order_number


def test_status_note_is_on_the_latest_event(db_session: Session, seeded: SeedCounts) -> None:
    ko_1009 = get_order(db_session, "KO-1009")
    assert ko_1009.events[-1].note == "Carrier weather delay."


def test_returned_order_has_a_refunded_return_request(db_session: Session, seeded: SeedCounts) -> None:
    ko_1010 = get_order(db_session, "KO-1010")
    [request] = ko_1010.return_requests
    assert request.status is ReturnStatus.REFUNDED
    assert request.items == [{"order_item_id": ko_1010.items[0].id, "quantity": 1}]


def test_next_order_number_continues_after_the_seed(db_session: Session, seeded: SeedCounts) -> None:
    assert make_order(db_session).order_number == "KO-1013"


def test_admin_user_is_created_with_a_hashed_password(db_session: Session, seeded: SeedCounts) -> None:
    admin = db_session.scalars(select(User)).one()
    assert admin.email == ADMIN_EMAIL
    assert admin.role is UserRole.ADMIN
    assert admin.password_hash != ADMIN_PASSWORD
    assert verify_password(admin.password_hash, ADMIN_PASSWORD)


def test_admin_is_skipped_without_credentials(db_session: Session) -> None:
    counts = seed_database(db_session, now=FIXED_NOW)
    assert counts.users == 0
    assert count(db_session, User) == 0


def test_short_admin_password_is_refused(db_session: Session) -> None:
    with pytest.raises(ValueError, match="at least 12"):
        seed_database(db_session, now=FIXED_NOW, admin_email=ADMIN_EMAIL, admin_password="short")


def test_reset_then_seed_again_gives_the_same_data(db_session: Session, seeded: SeedCounts) -> None:
    reset_database(db_session)
    again = seed_database(db_session, now=FIXED_NOW, admin_email=ADMIN_EMAIL, admin_password=ADMIN_PASSWORD)
    assert again == seeded


# --- the CLI command -------------------------------------------------------------------------


def test_cli_seed_reset(app: Flask, db_session: Session) -> None:
    result = app.test_cli_runner().invoke(args=["seed", "--reset"])
    assert result.exit_code == 0, result.output
    assert "Seeded 20 products, 217 variants, 12 orders" in result.output


def test_cli_seed_refuses_to_overwrite_existing_data(app: Flask, db_session: Session, seeded: SeedCounts) -> None:
    result = app.test_cli_runner().invoke(args=["seed"])
    assert result.exit_code == 1
    assert "flask seed --reset" in result.output


# --- timeline rules (pure function, no database) -----------------------------------------------


@pytest.mark.parametrize("status", list(OrderStatus))
def test_timeline_ends_in_every_possible_status(status: OrderStatus) -> None:
    created = FIXED_NOW - timedelta(days=20)
    delivered = FIXED_NOW - timedelta(days=10)
    timeline = build_order_timeline(status, created_at=created, now=FIXED_NOW, delivered_at=delivered)
    assert timeline[0].status is OrderStatus.PENDING_PAYMENT
    assert timeline[-1].status is status


def test_timeline_rejects_impossible_dates() -> None:
    # Delivered before it could have shipped (shipping takes a day).
    created = FIXED_NOW - timedelta(days=5)
    with pytest.raises(ValueError, match="impossible"):
        build_order_timeline(
            OrderStatus.DELIVERED, created_at=created, now=FIXED_NOW, delivered_at=created + timedelta(hours=1)
        )
