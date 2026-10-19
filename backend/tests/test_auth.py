"""Signup, login, logout, /me: cookies, CSRF, enumeration resistance and rate limits."""

from flask.testing import FlaskClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.security import verify_password
from tests.conftest import CUSTOMER_EMAIL, CUSTOMER_PASSWORD, csrf_headers

SIGNUP = {"email": "New.Person@Example.com", "password": "a-long-password", "name": "New Person"}


def set_cookie_headers(response) -> list[str]:  # type: ignore[no-untyped-def]
    return response.headers.getlist("Set-Cookie")


# --- signup -----------------------------------------------------------------------------------


def test_signup_creates_user_and_logs_in(client: FlaskClient, db_session: Session) -> None:
    response = client.post("/api/auth/signup", json=SIGNUP)

    assert response.status_code == 201
    assert response.get_json()["user"]["email"] == "new.person@example.com"
    user = db_session.scalars(select(User)).one()
    assert user.password_hash != SIGNUP["password"]
    assert verify_password(user.password_hash, SIGNUP["password"])
    assert client.get("/api/auth/me").get_json()["user"]["name"] == "New Person"


def test_session_cookie_is_httponly_and_samesite(client: FlaskClient, db_session: Session) -> None:
    response = client.post("/api/auth/signup", json=SIGNUP)
    cookies = {header.split("=", 1)[0]: header for header in set_cookie_headers(response)}

    session_cookie = cookies["access_token_cookie"]
    assert "HttpOnly" in session_cookie  # JavaScript can't read the session
    assert "SameSite=Lax" in session_cookie
    # The CSRF cookie must be readable by our own JavaScript, so it is NOT httpOnly.
    assert "HttpOnly" not in cookies["csrf_access_token"]


def test_session_cookie_expires_with_the_token(client: FlaskClient, db_session: Session) -> None:
    response = client.post("/api/auth/signup", json=SIGNUP)
    session_cookie = next(h for h in set_cookie_headers(response) if h.startswith("access_token_cookie="))
    assert "Max-Age=604800" in session_cookie  # 7 days, the same as the JWT's own expiry


def test_signup_with_existing_email_is_409(client: FlaskClient, customer: User) -> None:
    response = client.post("/api/auth/signup", json={**SIGNUP, "email": CUSTOMER_EMAIL.upper()})
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "email_taken"


def test_signup_validation(client: FlaskClient, db_session: Session) -> None:
    for body in (
        {**SIGNUP, "password": "short"},
        {**SIGNUP, "password": "x" * 129},
        {**SIGNUP, "email": "not-an-email"},
        {**SIGNUP, "name": "   "},
    ):
        response = client.post("/api/auth/signup", json=body)
        assert response.status_code == 400, body
        assert response.get_json()["error"]["code"] == "validation_error"


def test_auth_endpoints_require_json(client: FlaskClient, db_session: Session) -> None:
    # A cross-site HTML form can only send form-encoded data. Refusing it blocks login CSRF.
    response = client.post("/api/auth/login", data={"email": CUSTOMER_EMAIL, "password": "x"})
    assert response.status_code == 415
    assert response.get_json()["error"]["code"] == "unsupported_media_type"


# --- login ------------------------------------------------------------------------------------


def test_login_with_correct_password(client: FlaskClient, customer: User) -> None:
    response = client.post("/api/auth/login", json={"email": "  SAM@example.com ", "password": CUSTOMER_PASSWORD})
    assert response.status_code == 200
    assert response.get_json()["user"]["email"] == CUSTOMER_EMAIL
    assert client.get_cookie("access_token_cookie") is not None


def test_wrong_password_and_unknown_email_look_identical(client: FlaskClient, customer: User) -> None:
    wrong_password = client.post("/api/auth/login", json={"email": CUSTOMER_EMAIL, "password": "wrong-password"})
    unknown_email = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"})

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.get_json() == unknown_email.get_json()
    assert client.get_cookie("access_token_cookie") is None


def test_login_is_rate_limited_per_ip(client: FlaskClient, customer: User) -> None:
    attempts = [
        client.post("/api/auth/login", json={"email": f"user{n}@example.com", "password": "wrong"}).status_code
        for n in range(6)
    ]
    assert attempts == [401] * 5 + [429]


def test_login_is_rate_limited_per_account_across_ips(client: FlaskClient, customer: User) -> None:
    statuses = []
    for n in range(11):
        # A different client IP each time, as in a distributed attack.
        environ = {"REMOTE_ADDR": f"10.0.0.{n}"}
        body = {"email": CUSTOMER_EMAIL, "password": "wrong"}
        statuses.append(client.post("/api/auth/login", json=body, environ_base=environ).status_code)
    assert statuses[-1] == 429
    assert statuses[:10] == [401] * 10


def test_rate_limit_response_uses_the_json_error_shape(client: FlaskClient, customer: User) -> None:
    for _ in range(6):
        response = client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong"})
    assert response.status_code == 429
    assert response.get_json()["error"]["code"] == "too_many_requests"
    assert "Retry-After" in response.headers


# --- me / logout ------------------------------------------------------------------------------


def test_me_when_logged_out_is_null(client: FlaskClient, db_session: Session) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.get_json() == {"user": None}
    assert response.headers["Cache-Control"] == "no-store"


def test_logout_clears_the_session(logged_in: FlaskClient) -> None:
    response = logged_in.post("/api/auth/logout")
    assert response.status_code == 200
    assert logged_in.get("/api/auth/me").get_json() == {"user": None}


def test_tampered_token_is_rejected_and_cleared(logged_in: FlaskClient) -> None:
    token = logged_in.get_cookie("access_token_cookie")
    assert token is not None
    logged_in.set_cookie("access_token_cookie", token.value[:-4] + "AAAA")  # break the signature

    response = logged_in.get("/api/auth/me")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_session"


def test_deleted_user_session_is_rejected(logged_in: FlaskClient, db_session: Session, customer: User) -> None:
    db_session.delete(customer)
    db_session.commit()
    assert logged_in.get("/api/auth/me").status_code == 401


# --- CSRF -------------------------------------------------------------------------------------


ADDRESS = {"name": "Sam", "line1": "1 Main St", "city": "Austin", "state": "TX", "postal_code": "78701", "country": "US"}


def test_writes_without_csrf_header_are_refused(logged_in: FlaskClient) -> None:
    response = logged_in.post("/api/account/addresses", json=ADDRESS)
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "csrf_failed"


def test_writes_with_wrong_csrf_header_are_refused(logged_in: FlaskClient) -> None:
    response = logged_in.post("/api/account/addresses", json=ADDRESS, headers={"X-CSRF-TOKEN": "guess"})
    assert response.status_code == 403


def test_writes_with_csrf_header_succeed(logged_in: FlaskClient) -> None:
    response = logged_in.post("/api/account/addresses", json=ADDRESS, headers=csrf_headers(logged_in))
    assert response.status_code == 201


def test_reads_do_not_need_csrf(logged_in: FlaskClient) -> None:
    assert logged_in.get("/api/account/addresses").status_code == 200


def test_rehashes_outdated_password_hash_on_login(client: FlaskClient, db_session: Session, customer: User) -> None:
    from argon2 import PasswordHasher

    weak = PasswordHasher(time_cost=1, memory_cost=8192).hash(CUSTOMER_PASSWORD)
    customer.password_hash = weak
    db_session.commit()

    assert client.post("/api/auth/login", json={"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD}).status_code == 200
    db_session.refresh(customer)
    assert customer.password_hash != weak
    assert verify_password(customer.password_hash, CUSTOMER_PASSWORD)
