"""A customer sees only orders placed by their own account."""

from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from app.models import User
from tests.factories import make_order


def test_requires_login(client: FlaskClient, db_session: Session) -> None:
    assert client.get("/api/account/orders").status_code == 401


def test_lists_only_my_orders(logged_in: FlaskClient, db_session: Session, customer: User) -> None:
    mine = make_order(db_session, user=customer)
    # A guest order using the SAME email must not appear: emails aren't verified, so matching
    # by email would let anyone who signs up with your address read your orders.
    make_order(db_session, email=customer.email)
    db_session.commit()

    orders = logged_in.get("/api/account/orders").get_json()
    assert [order["order_number"] for order in orders] == [mine.order_number]


def test_order_detail(logged_in: FlaskClient, db_session: Session, customer: User) -> None:
    order = make_order(db_session, user=customer)
    db_session.commit()

    body = logged_in.get(f"/api/account/orders/{order.order_number.lower()}").get_json()
    assert body["order_number"] == order.order_number
    assert body["total_cents"] == 3095
    assert body["shipping_address"]["city"] == "Austin"


def test_other_peoples_orders_are_404(logged_in: FlaskClient, db_session: Session) -> None:
    guest = make_order(db_session)
    db_session.commit()
    assert logged_in.get(f"/api/account/orders/{guest.order_number}").status_code == 404
