"""Saved addresses: CRUD, the one-default rule, ownership and validation."""

from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from app.accounts import MAX_ADDRESSES
from app.models import Address, User
from app.security import hash_password
from tests.conftest import csrf_headers
from tests.factories import make_user

HOME = {"name": "Sam", "line1": "1 Main St", "city": "Austin", "state": "TX", "postal_code": "78701", "country": "US"}
WORK = {**HOME, "name": "Sam (work)", "line1": "9 Office Rd"}


def add(client: FlaskClient, body: dict) -> dict:  # type: ignore[type-arg]
    response = client.post("/api/account/addresses", json=body, headers=csrf_headers(client))
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def test_requires_login(client: FlaskClient, db_session: Session) -> None:
    response = client.get("/api/account/addresses")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "not_authenticated"


def test_first_address_becomes_default(logged_in: FlaskClient) -> None:
    assert add(logged_in, HOME)["is_default"] is True
    assert add(logged_in, WORK)["is_default"] is False


def test_making_another_address_default_moves_the_flag(logged_in: FlaskClient) -> None:
    home = add(logged_in, HOME)
    work = add(logged_in, {**WORK, "is_default": True})

    listed = logged_in.get("/api/account/addresses").get_json()
    assert [(a["id"], a["is_default"]) for a in listed] == [(work["id"], True), (home["id"], False)]


def test_update_address(logged_in: FlaskClient) -> None:
    home = add(logged_in, HOME)
    response = logged_in.put(
        f"/api/account/addresses/{home['id']}", json={**HOME, "city": "Dallas"}, headers=csrf_headers(logged_in)
    )
    assert response.status_code == 200
    assert response.get_json()["city"] == "Dallas"


def test_deleting_the_default_promotes_another(logged_in: FlaskClient) -> None:
    home = add(logged_in, HOME)
    work = add(logged_in, WORK)
    response = logged_in.delete(f"/api/account/addresses/{home['id']}", headers=csrf_headers(logged_in))
    assert response.status_code == 204

    [remaining] = logged_in.get("/api/account/addresses").get_json()
    assert remaining["id"] == work["id"]
    assert remaining["is_default"] is True


def test_cannot_read_or_change_another_users_address(logged_in: FlaskClient, db_session: Session) -> None:
    other = make_user(db_session, email="other@example.com", password_hash=hash_password("another-password"))
    theirs = Address(user=other, **HOME)
    db_session.add(theirs)
    db_session.commit()

    headers = csrf_headers(logged_in)
    assert logged_in.put(f"/api/account/addresses/{theirs.id}", json=WORK, headers=headers).status_code == 404
    assert logged_in.delete(f"/api/account/addresses/{theirs.id}", headers=headers).status_code == 404
    assert logged_in.get("/api/account/addresses").get_json() == []


def test_address_validation(logged_in: FlaskClient) -> None:
    for body in ({**HOME, "country": "FR"}, {**HOME, "state": None}, {**HOME, "line1": "  "}):
        response = logged_in.post("/api/account/addresses", json=body, headers=csrf_headers(logged_in))
        assert response.status_code == 400, body


def test_non_us_address_without_state_is_fine(logged_in: FlaskClient) -> None:
    uk = {"name": "Sam", "line1": "10 High St", "city": "London", "postal_code": "N1 9GU", "country": "GB"}
    assert add(logged_in, uk)["state"] is None


def test_address_limit(logged_in: FlaskClient, customer: User, db_session: Session) -> None:
    db_session.add_all(Address(user=customer, **HOME) for _ in range(MAX_ADDRESSES))
    db_session.commit()
    response = logged_in.post("/api/account/addresses", json=HOME, headers=csrf_headers(logged_in))
    assert response.status_code == 409
