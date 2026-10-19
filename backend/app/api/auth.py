"""Accounts and sessions.

POST   /api/auth/signup                create an account and log in
POST   /api/auth/login                 log in
POST   /api/auth/logout                log out (clears the cookies)
GET    /api/auth/me                    the logged-in user, or {"user": null}
GET    /api/account/addresses          saved addresses
POST   /api/account/addresses          add an address
PUT    /api/account/addresses/<id>     edit an address
DELETE /api/account/addresses/<id>     delete an address
"""

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy.exc import IntegrityError

from app import accounts
from app.accounts import AddressBody, LoginBody, SignupBody
from app.errors import APIError
from app.extensions import db, limiter
from app.models import User, normalize_email
from app.security import DUMMY_PASSWORD_HASH, hash_password, password_needs_rehash, verify_password
from app.sessions import end_session, start_session, user_dict
from app.validation import parse_json

bp = Blueprint("auth", __name__)


def _login_email_key() -> str:
    """Rate-limit key for one account, whichever IP the attempts come from."""
    body = request.get_json(silent=True)
    email = body.get("email") if isinstance(body, dict) else None
    return f"login-email:{normalize_email(email)}" if isinstance(email, str) else "login-email:none"


@bp.post("/auth/signup")
@limiter.limit("10 per hour")  # per IP: slows down mass account creation
def signup() -> ResponseReturnValue:
    body = parse_json(SignupBody)
    if accounts.find_user_by_email(db.session, body.email):
        # Telling the visitor the email is taken does reveal that an account exists. Every shop
        # does this at signup (the alternative is email verification); login never reveals it.
        raise APIError("email_taken", "An account with this email already exists. Try logging in.", 409)

    user = User(email=body.email, password_hash=hash_password(body.password), name=body.name)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:  # two signups with the same email at the same moment
        db.session.rollback()
        raise APIError("email_taken", "An account with this email already exists. Try logging in.", 409)

    response = jsonify(user=user_dict(user))
    response.status_code = 201
    start_session(response, user)
    return response


@bp.post("/auth/login")
@limiter.limit("5 per minute; 30 per hour")  # per IP
@limiter.limit("10 per hour", key_func=_login_email_key)  # per account, against many-IP attacks
def login() -> ResponseReturnValue:
    body = parse_json(LoginBody)
    user = accounts.find_user_by_email(db.session, body.email)

    if user is None:
        verify_password(DUMMY_PASSWORD_HASH, body.password)  # same work, same timing
        valid = False
    else:
        valid = verify_password(user.password_hash, body.password)
    if not valid or user is None:
        # One message for both cases, so login can't be used to test which emails have accounts.
        raise APIError("invalid_credentials", "Wrong email or password.", 401)

    if password_needs_rehash(user.password_hash):
        # We only ever see the plain password at login, so this is when stronger settings apply.
        user.password_hash = hash_password(body.password)
        db.session.commit()

    response = jsonify(user=user_dict(user))
    start_session(response, user)
    return response


@bp.post("/auth/logout")
def logout() -> ResponseReturnValue:
    # No login required: clearing cookies is always safe, even with an expired session.
    response = jsonify(ok=True)
    end_session(response)
    return response


@bp.get("/auth/me")
@jwt_required(optional=True)
def me() -> ResponseReturnValue:
    # 200 with null (not 401) when logged out: "who am I?" has a valid answer either way.
    return {"user": user_dict(current_user) if current_user else None}


@bp.get("/account/addresses")
@jwt_required()
def list_addresses() -> ResponseReturnValue:
    return jsonify([accounts.address_dict(a) for a in accounts.list_addresses(db.session, current_user)])


@bp.post("/account/addresses")
@jwt_required()
def create_address() -> ResponseReturnValue:
    address = accounts.create_address(db.session, current_user, parse_json(AddressBody))
    return accounts.address_dict(address), 201


@bp.put("/account/addresses/<int:address_id>")
@jwt_required()
def update_address(address_id: int) -> ResponseReturnValue:
    address = accounts.update_address(db.session, current_user, address_id, parse_json(AddressBody))
    return accounts.address_dict(address)


@bp.delete("/account/addresses/<int:address_id>")
@jwt_required()
def delete_address(address_id: int) -> ResponseReturnValue:
    accounts.delete_address(db.session, current_user, address_id)
    return "", 204
