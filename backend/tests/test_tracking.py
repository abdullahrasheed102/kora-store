"""POST /api/orders/track: found, not found (identically), and rate limited."""

from typing import Any

import pytest
from flask.testing import FlaskClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order
from app.returns import normalize_order_number
from app.seed import SeedCounts


def email_of(session: Session, number: str) -> str:
    return session.scalars(select(Order.email).where(Order.order_number == number)).one()


def track(client: FlaskClient, number: str, email: str, **kwargs: Any) -> Any:
    return client.post("/api/orders/track", json={"order_number": number, "email": email}, **kwargs)


def test_tracking_shows_status_and_timeline(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    response = track(client, "KO-1009", email_of(db_session, "KO-1009"))
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "delayed"
    assert body["status_note"] == "Carrier weather delay."
    assert body["carrier"] == "USPS"
    assert [e["status"] for e in body["events"]] == ["pending_payment", "processing", "shipped", "delayed"]


def test_tracking_reveals_no_street_address(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    body = track(client, "KO-1009", email_of(db_session, "KO-1009")).get_json()
    assert "123 Demo Street" not in str(body)
    assert "shipping_line1" not in body and "stripe_payment_intent" not in body


@pytest.mark.parametrize("number", ["1009", " ko-1009 ", "KO-1009"])
def test_order_number_and_email_are_forgiving(client: FlaskClient, db_session: Session, seeded: SeedCounts, number: str) -> None:
    assert track(client, number, email_of(db_session, "KO-1009").upper()).status_code == 200


def test_wrong_email_and_unknown_order_look_identical(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    wrong_email = track(client, "KO-1009", "someone.else@example.com")
    unknown_order = track(client, "KO-9999", email_of(db_session, "KO-1009"))
    garbage_number = track(client, "DROP TABLE", email_of(db_session, "KO-1009"))

    assert wrong_email.status_code == unknown_order.status_code == garbage_number.status_code == 404
    assert wrong_email.get_json() == unknown_order.get_json() == garbage_number.get_json()
    assert wrong_email.get_json()["error"]["code"] == "order_not_found"


def test_tracking_is_rate_limited_per_ip(client: FlaskClient, seeded: SeedCounts) -> None:
    statuses = [track(client, f"KO-{2000 + n}", "a@example.com").status_code for n in range(11)]
    assert statuses == [404] * 10 + [429]


def test_guessing_emails_for_one_order_is_limited_across_ips(client: FlaskClient, seeded: SeedCounts) -> None:
    statuses = [
        track(client, "KO-1005", f"guess{n}@example.com", environ_base={"REMOTE_ADDR": f"10.1.0.{n}"}).status_code
        for n in range(21)
    ]
    assert statuses[:20] == [404] * 20
    assert statuses[20] == 429


def test_tracking_and_returns_share_one_budget(client: FlaskClient, seeded: SeedCounts) -> None:
    for n in range(10):
        track(client, f"KO-{2000 + n}", "a@example.com")
    response = client.post("/api/returns/eligibility", json={"order_number": "KO-3000", "email": "a@example.com"})
    assert response.status_code == 429


def test_tracking_needs_an_email(client: FlaskClient, seeded: SeedCounts) -> None:
    assert client.post("/api/orders/track", json={"order_number": "KO-1009"}).status_code == 400


def test_normalize_order_number() -> None:
    assert normalize_order_number(" ko-1005 ") == "KO-1005"
    assert normalize_order_number("1005") == "KO-1005"
    assert normalize_order_number("KO-10a5") is None
    assert normalize_order_number("") is None


def test_successful_lookups_do_not_use_up_the_limit(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    # A real customer checking their order many times is never blocked: only misses count.
    email = email_of(db_session, "KO-1009")
    assert all(track(client, "KO-1009", email).status_code == 200 for _ in range(15))
    # ...while guesses still are.
    statuses = [track(client, f"KO-{3000 + n}", email).status_code for n in range(11)]
    assert statuses[-1] == 429
