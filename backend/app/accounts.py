"""Customer accounts: signup/login input rules, saved addresses, and order history.

Everything here is scoped to one user. Lookups always filter by user_id, so asking for
someone else's address or order gives "not found", never their data (this prevents IDOR:
Insecure Direct Object Reference, i.e. guessing another user's ids).
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.errors import APIError
from app.models import Address, Order, User
from app.returns import return_view

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None

MIN_PASSWORD_LENGTH = 10
# argon2 handles long inputs fine, but an unlimited length lets one request burn a lot of CPU.
MAX_PASSWORD_LENGTH = 128
MAX_ADDRESSES = 10
# Countries we ship to (shipping policy: US, UK, Canada, Australia).
ShippingCountry = Literal["US", "GB", "CA", "AU"]


# --- request bodies ---------------------------------------------------------------------------


class SignupBody(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    name: Annotated[Text, StringConstraints(max_length=120)]


class LoginBody(BaseModel):
    # Plain str, not EmailStr: a login form should just say "wrong email or password",
    # not explain which part was malformed.
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class AddressBody(BaseModel):
    name: Annotated[Text, StringConstraints(max_length=120)]
    line1: Annotated[Text, StringConstraints(max_length=200)]
    line2: OptionalText = None
    city: Annotated[Text, StringConstraints(max_length=100)]
    state: OptionalText = None
    postal_code: Annotated[Text, StringConstraints(max_length=20)]
    country: ShippingCountry
    is_default: bool = False

    @model_validator(mode="after")
    def _us_needs_state(self) -> "AddressBody":
        if self.country == "US" and not self.state:
            raise ValueError("state is required for US addresses")
        self.line2 = self.line2 or None
        self.state = self.state or None
        return self


# --- users ------------------------------------------------------------------------------------


def find_user_by_email(session: Session, email: str) -> User | None:
    return session.scalars(select(User).where(User.email == email.strip().lower())).one_or_none()


# --- addresses --------------------------------------------------------------------------------


def address_dict(address: Address) -> dict[str, Any]:
    return {
        "id": address.id,
        "name": address.name,
        "line1": address.line1,
        "line2": address.line2,
        "city": address.city,
        "state": address.state,
        "postal_code": address.postal_code,
        "country": address.country,
        "is_default": address.is_default,
    }


def list_addresses(session: Session, user: User) -> list[Address]:
    # Default first, then oldest first.
    return list(
        session.scalars(
            select(Address).where(Address.user_id == user.id).order_by(Address.is_default.desc(), Address.id)
        )
    )


def get_address(session: Session, user: User, address_id: int) -> Address:
    address = session.scalars(
        select(Address).where(Address.id == address_id, Address.user_id == user.id)
    ).one_or_none()
    if address is None:
        raise APIError("address_not_found", "Address not found.", 404)
    return address


def create_address(session: Session, user: User, body: AddressBody) -> Address:
    count = session.scalar(select(func.count()).select_from(Address).where(Address.user_id == user.id)) or 0
    if count >= MAX_ADDRESSES:
        raise APIError("too_many_addresses", f"You can save up to {MAX_ADDRESSES} addresses.", 409)

    address = Address(user_id=user.id, **body.model_dump(exclude={"is_default"}))
    session.add(address)
    # The first address is always the default.
    _set_default_flag(session, user, address, body.is_default or count == 0)
    session.commit()
    return address


def update_address(session: Session, user: User, address_id: int, body: AddressBody) -> Address:
    address = get_address(session, user, address_id)
    for field, value in body.model_dump(exclude={"is_default"}).items():
        setattr(address, field, value)
    # You can't "un-default" your only default; pick another address as default instead.
    if body.is_default:
        _set_default_flag(session, user, address, True)
    session.commit()
    return address


def delete_address(session: Session, user: User, address_id: int) -> None:
    address = get_address(session, user, address_id)
    was_default = address.is_default
    session.delete(address)
    session.flush()
    if was_default:  # promote the oldest remaining address, so there's still a default
        replacement = session.scalars(
            select(Address).where(Address.user_id == user.id).order_by(Address.id).limit(1)
        ).one_or_none()
        if replacement:
            replacement.is_default = True
    session.commit()


def _set_default_flag(session: Session, user: User, address: Address, make_default: bool) -> None:
    if make_default:
        # Clear the old default first, in the same transaction. The partial unique index
        # (one default per user) would reject two defaults even for a moment.
        session.execute(
            update(Address).where(Address.user_id == user.id, Address.is_default).values(is_default=False)
        )
    address.is_default = make_default


# --- order history ----------------------------------------------------------------------------


def order_summary(order: Order) -> dict[str, Any]:
    return {
        "order_number": order.order_number,
        "status": order.status.value,
        "payment_method": order.payment_method.value,
        "payment_status": order.payment_status.value,
        "total_cents": order.total_cents,
        "item_count": sum(item.quantity for item in order.items),
        "created_at": order.created_at.isoformat(),
    }


def order_detail(order: Order) -> dict[str, Any]:
    return {
        **order_summary(order),
        "status_note": order.status_note,
        "email": order.email,
        "customer_name": order.customer_name,
        "subtotal_cents": order.subtotal_cents,
        "shipping_cents": order.shipping_cents,
        "shipping_method": order.shipping_method.value,
        "shipping_address": {
            "line1": order.shipping_line1,
            "line2": order.shipping_line2,
            "city": order.shipping_city,
            "state": order.shipping_state,
            "postal_code": order.shipping_postal_code,
            "country": order.shipping_country,
        },
        "carrier": order.carrier,
        "tracking_number": order.tracking_number,
        "estimated_delivery": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "items": [
            {
                "id": item.id,
                "product_name": item.product_name,
                "size": item.size,
                "color": item.color,
                "unit_price_cents": item.unit_price_cents,
                "quantity": item.quantity,
                "line_total_cents": item.line_total_cents,
                "is_final_sale": item.is_final_sale,
            }
            for item in order.items
        ],
        "events": [
            {"status": event.status.value, "note": event.note, "created_at": event.created_at.isoformat()}
            for event in order.events
        ],
        "returns": [return_view(request) for request in order.return_requests],
    }


def list_user_orders(session: Session, user: User) -> list[Order]:
    # Only orders placed while logged in to THIS account. We never match guest orders by email:
    # emails aren't verified, so anyone could sign up with your address and read your orders.
    return list(
        session.scalars(
            select(Order)
            .where(Order.user_id == user.id)
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc(), Order.id.desc())
        )
    )


def get_user_order(session: Session, user: User, order_number: str) -> Order:
    order = session.scalars(
        select(Order)
        .where(Order.order_number == order_number.upper(), Order.user_id == user.id)
        .options(selectinload(Order.items), selectinload(Order.events), selectinload(Order.return_requests))
    ).one_or_none()
    if order is None:
        raise APIError("order_not_found", "Order not found.", 404)
    return order
