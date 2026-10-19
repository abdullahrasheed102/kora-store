"""Newsletter.

POST /api/newsletter   {"email": "..."} -> subscribe
"""

from flask import Blueprint
from flask.typing import ResponseReturnValue
from pydantic import BaseModel, EmailStr, Field

from app import newsletter
from app.extensions import db, limiter
from app.validation import parse_json

bp = Blueprint("newsletter", __name__)

# The same answer for a new and an existing subscriber, so the form can't be used to find out
# whether someone is on our list.
SUCCESS_MESSAGE = "Thanks for subscribing! Look out for our next letter in your inbox."


class SubscribeBody(BaseModel):
    email: EmailStr = Field(max_length=254)


@bp.post("/newsletter")
@limiter.limit("5 per minute; 20 per hour")  # per IP: stops scripts filling the list with junk
def subscribe() -> ResponseReturnValue:
    body = parse_json(SubscribeBody)
    newsletter.subscribe(db.session, body.email)
    return {"message": SUCCESS_MESSAGE}
