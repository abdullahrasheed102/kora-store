"""Model rules, and the database constraints that back them up."""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Address, Order, OrderEvent, OrderItem, OrderStatus, User, UserRole
from tests.factories import make_order, make_product, make_user, make_variant


def test_migrations_match_models(db_session: Session) -> None:
    """If someone changes a model but forgets `flask db migrate`, this fails."""
    with db.engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), db.metadata)
    assert differences == []


# --- users ---------------------------------------------------------------------------------


def test_user_email_is_trimmed_and_lowercased(db_session: Session) -> None:
    user = make_user(db_session, email="  Emily.Carter@Example.COM ")
    assert user.email == "emily.carter@example.com"


def test_user_role_defaults_to_customer(db_session: Session) -> None:
    user = make_user(db_session)
    assert user.role is UserRole.CUSTOMER
    assert not user.is_admin


def test_emails_are_unique_ignoring_case(db_session: Session) -> None:
    make_user(db_session, email="sam@example.com")
    with pytest.raises(IntegrityError):
        make_user(db_session, email="SAM@example.com")


def test_database_rejects_mixed_case_email_from_raw_sql(db_session: Session) -> None:
    user = make_user(db_session)
    with pytest.raises(IntegrityError, match="ck_users_email_lowercase"):
        db_session.execute(text("UPDATE users SET email = 'Upper@Example.com' WHERE id = :id"), {"id": user.id})


def test_only_one_default_address_per_user(db_session: Session) -> None:
    user = make_user(db_session)
    address = {"name": "Home", "line1": "1 Main St", "city": "Austin", "postal_code": "78701", "country": "US"}
    db_session.add(Address(user=user, is_default=True, **address))
    db_session.add(Address(user=user, is_default=False, **address))
    db_session.flush()  # many non-default addresses are fine

    db_session.add(Address(user=user, is_default=True, **address))
    with pytest.raises(IntegrityError, match="uq_addresses_one_default_per_user"):
        db_session.flush()


def test_deleting_a_user_deletes_their_addresses(db_session: Session) -> None:
    user = make_user(db_session)
    db_session.add(Address(user=user, name="Home", line1="1 Main St", city="Austin", postal_code="78701", country="US"))
    db_session.flush()

    db_session.delete(user)
    db_session.flush()
    assert db_session.query(Address).count() == 0


# --- catalog -------------------------------------------------------------------------------


def test_stock_cannot_go_negative(db_session: Session) -> None:
    variant = make_variant(db_session, make_product(db_session), stock=1)
    variant.stock -= 2
    with pytest.raises(IntegrityError, match="ck_product_variants_stock_not_negative"):
        db_session.flush()


def test_size_and_color_are_unique_within_a_product(db_session: Session) -> None:
    product = make_product(db_session)
    make_variant(db_session, product, sku="A", size="M", color="White")
    with pytest.raises(IntegrityError, match="uq_product_variants_product_size_color"):
        make_variant(db_session, product, sku="B", size="M", color="White")


def test_variant_price_falls_back_to_product_price(db_session: Session) -> None:
    product = make_product(db_session, price_cents=2500)
    normal = make_variant(db_session, product, sku="A", size="$25")
    override = make_variant(db_session, product, sku="B", size="$100", price_cents=10000)
    assert normal.effective_price_cents == 2500
    assert override.effective_price_cents == 10000


# --- orders --------------------------------------------------------------------------------


def test_order_numbers_come_from_the_sequence(db_session: Session) -> None:
    first = make_order(db_session)
    second = make_order(db_session)
    assert first.order_number == "KO-1001"
    assert second.order_number == "KO-1002"


def test_new_order_starts_as_pending_payment(db_session: Session) -> None:
    assert make_order(db_session).status is OrderStatus.PENDING_PAYMENT


def test_order_total_must_equal_subtotal_plus_shipping(db_session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_orders_total_adds_up"):
        make_order(db_session, subtotal_cents=1000, shipping_cents=695, total_cents=1000)


def test_database_rejects_unknown_order_status(db_session: Session) -> None:
    order = make_order(db_session)
    with pytest.raises(IntegrityError, match="ck_orders_order_status"):
        db_session.execute(text("UPDATE orders SET status = 'lost' WHERE id = :id"), {"id": order.id})


def test_order_item_quantity_must_be_positive(db_session: Session) -> None:
    order = make_order(db_session)
    db_session.add(OrderItem(order=order, product_name="Tee", size="M", color="White", unit_price_cents=2400, quantity=0))
    with pytest.raises(IntegrityError, match="ck_order_items_quantity_positive"):
        db_session.flush()


def test_order_events_are_returned_oldest_first(db_session: Session) -> None:
    order = make_order(db_session)
    db_session.add_all(
        [
            OrderEvent(order=order, status=OrderStatus.PROCESSING, created_at=text("now()")),
            OrderEvent(order=order, status=OrderStatus.PENDING_PAYMENT, created_at=text("now() - interval '1 hour'")),
        ]
    )
    db_session.commit()
    db_session.expire_all()

    reloaded = db_session.get(Order, order.id)
    assert reloaded is not None
    assert [event.status for event in reloaded.events] == [OrderStatus.PENDING_PAYMENT, OrderStatus.PROCESSING]


def test_order_survives_deleting_the_user(db_session: Session) -> None:
    user = make_user(db_session)
    order = make_order(db_session, user=user)
    db_session.delete(user)
    db_session.flush()
    db_session.refresh(order)
    assert order.user_id is None
