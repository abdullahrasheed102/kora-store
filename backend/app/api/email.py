"""Email verification, and the outbox retry job.

POST /api/email/verify                a "confirm your email" link was clicked (token in the body)
POST /api/email/resend-verification   send the account's verification email again (logged in)
POST /api/email/change                "wrong email?": fix the address of an unconfirmed account (logged in)
POST /api/email/outbox/process        the scheduled retry job (Authorization: Bearer OUTBOX_CRON_SECRET)
"""

import hmac

from flask import Blueprint, current_app, request
from flask.typing import ResponseReturnValue
from flask_jwt_extended import current_user, get_current_user, jwt_required
from pydantic import BaseModel, Field

from app import accounts, notifications
from app.accounts import ChangeEmailBody
from app.errors import APIError
from app.extensions import db, limiter
from app.mail import outbox, verification
from app.sessions import user_dict
from app.validation import parse_json

bp = Blueprint("email", __name__)


class VerifyBody(BaseModel):
    token: str = Field(min_length=10, max_length=1000)


@bp.post("/email/verify")
@limiter.limit("20 per hour")  # per IP; tokens are signed, so this only slows down noise
@jwt_required(optional=True)  # works logged out too (e.g. the link opened on another device)
def verify() -> ResponseReturnValue:
    # A POST from a button on /verify-email, not a GET on the link itself: mail scanners open
    # links in emails automatically, and a GET that changes data would be triggered by them.
    body = parse_json(VerifyBody)
    email = verification.confirm_email(db.session, body.token, outbox.utc_now())
    user = get_current_user()
    # Tells the page where to go next: the account page if this browser is logged in as the
    # owner of the address, otherwise the login page.
    return {"verified": True, "email": email, "signed_in": user is not None and user.email == email}


@bp.post("/email/resend-verification")
# Per IP. The check-your-email page shows a countdown from the Retry-After header we send.
@limiter.limit("1 per minute; 5 per hour")
@jwt_required()
def resend_verification() -> ResponseReturnValue:
    if current_user.email_verified:
        return {"sent": False, "already_verified": True}
    notifications.account_verification(db.session, current_user)
    db.session.commit()
    return {"sent": True, "already_verified": False}


@bp.post("/email/change")
@limiter.limit("5 per hour")  # per IP: each change sends an email
@jwt_required()
def change_email() -> ResponseReturnValue:
    user = accounts.change_unconfirmed_email(db.session, current_user, parse_json(ChangeEmailBody))
    return {"user": user_dict(user)}


@bp.post("/email/outbox/process")
def process_outbox() -> ResponseReturnValue:
    """Called every 5 minutes by .github/workflows/email-outbox.yml."""
    secret = current_app.config["OUTBOX_CRON_SECRET"]
    if not secret:
        raise APIError("not_found", "Not found.", 404)  # switched off until a secret is configured
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
    # compare_digest takes the same time whether the first or the last character is wrong, so
    # the response time can't be used to guess the secret one character at a time.
    if not hmac.compare_digest(supplied.encode(), secret.encode()):
        raise APIError("unauthorized", "A valid bearer token is required.", 401)
    return outbox.run_scheduled(db.session, force=request.args.get("force") == "1")
