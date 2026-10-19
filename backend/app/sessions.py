"""Login sessions: JWTs stored in httpOnly cookies, via Flask-JWT-Extended.

How a session works:
1. Login/signup calls start_session(). It sets two cookies:
   - access_token_cookie: the signed JWT. httpOnly, so JavaScript (and any XSS script) can't read it.
   - csrf_access_token: a random value that JavaScript CAN read. The JWT contains the same value.
2. On POST/PUT/PATCH/DELETE, the frontend copies csrf_access_token into the X-CSRF-TOKEN header.
   Flask-JWT-Extended checks the header matches the value inside the JWT. Another website can make
   the browser *send* our cookies, but it can't *read* them, so it can't set the header.
3. The JWT only holds the user id. The user is loaded from the database on each request, so a role
   change or a deleted account takes effect immediately.
"""

from typing import Any

from flask import Flask, Response, jsonify
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies

from app.extensions import db, jwt
from app.models import User


def start_session(response: Response, user: User) -> None:
    set_access_cookies(response, create_access_token(identity=str(user.id)))


def end_session(response: Response) -> None:
    unset_jwt_cookies(response)


def user_dict(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role.value,
        "created_at": user.created_at.isoformat(),
    }


def _error(code: str, message: str, status: int, *, clear_cookies: bool = False) -> Response:
    response = jsonify(error={"code": code, "message": message})
    response.status_code = status
    if clear_cookies:  # a broken or expired session cookie is useless; remove it
        end_session(response)
    return response


def register_jwt_callbacks(app: Flask) -> None:
    """Load the user for each request, and return our JSON error shape for every session problem."""

    @jwt.user_lookup_loader
    def load_user(_header: dict[str, Any], payload: dict[str, Any]) -> User | None:
        return db.session.get(User, int(payload["sub"]))

    @jwt.unauthorized_loader
    def missing_session(reason: str) -> Response:
        # Flask-JWT-Extended also sends CSRF failures here.
        if "CSRF" in reason:
            return _error("csrf_failed", "Security check failed. Refresh the page and try again.", 403)
        return _error("not_authenticated", "Please log in.", 401)

    @jwt.invalid_token_loader
    def invalid_session(_reason: str) -> Response:
        return _error("invalid_session", "Your session is not valid. Please log in again.", 401, clear_cookies=True)

    @jwt.expired_token_loader
    def expired_session(_header: dict[str, Any], _payload: dict[str, Any]) -> Response:
        return _error("session_expired", "Your session has expired. Please log in again.", 401, clear_cookies=True)

    @jwt.user_lookup_error_loader
    def deleted_user(_header: dict[str, Any], _payload: dict[str, Any]) -> Response:
        return _error("invalid_session", "Your account was not found. Please log in again.", 401, clear_cookies=True)
