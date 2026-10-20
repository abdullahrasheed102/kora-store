"""Sample data for `flask email preview`: render any email to a file you can open in a browser.

The samples are ordinary model objects that are never added to a database session, run through
the SAME context functions the real notifications use (app/notifications.py). So a preview shows
exactly what a customer would get, and needs no database.
"""

from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app import notifications
from app.mail.render import Rendered, render
from app.mail.verification import make_token, verify_url
from app.models import (
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    ReturnRequest,
    ReturnStatus,
    ReturnType,
    ShippingMethod,
    SupportTicket,
    TicketPriority,
    TicketSource,
)

PREVIEW_EMAIL = "maya.chen@example.com"


def sample_order(*, cod: bool = False) -> Order:
    order = Order(
        id=1013,
        order_number="KO-1013",
        email=PREVIEW_EMAIL,
        customer_name="Maya Chen",
        payment_method=PaymentMethod.COD if cod else PaymentMethod.CARD,
        subtotal_cents=11600,
        shipping_cents=0,
        total_cents=11600,
        shipping_method=ShippingMethod.STANDARD,
        shipping_line1="214 Elm Street",
        shipping_line2="Apt 3B",
        shipping_city="Portland",
        shipping_state="OR",
        shipping_postal_code="97205",
        shipping_country="US",
        carrier="UPS",
        tracking_number="1Z999AA10123456784",
        estimated_delivery=date.today() + timedelta(days=3),
        items=[
            OrderItem(id=1, product_name="Linen Button-Up Shirt", size="M", color="Sand", unit_price_cents=5800, quantity=1),
            OrderItem(id=2, product_name="Everyday Cotton Tee", size="S", color="White", unit_price_cents=2400, quantity=2),
            OrderItem(id=3, product_name="Ribbed Tank Top", size="S", color="White", unit_price_cents=1000, quantity=1),
        ],
    )
    return order


def sample_return(*, exchange: bool = False) -> ReturnRequest:
    order = sample_order()
    if exchange:
        return ReturnRequest(
            id=7, order=order, items=[{"order_item_id": 1, "quantity": 1}], reason="Too small",
            type=ReturnType.EXCHANGE, exchange_details="Exchange for L / Sand (SKU LBS-SAND-L)", status=ReturnStatus.APPROVED,
        )
    return ReturnRequest(
        id=7, order=order, items=[{"order_item_id": 2, "quantity": 2}], reason="Didn't suit me",
        type=ReturnType.REFUND, status=ReturnStatus.APPROVED,
    )


def _with_note(order: Order, note: str) -> Order:
    order.status_note = note
    return order


def _ticket() -> SupportTicket:
    return SupportTicket(
        id=42, email=PREVIEW_EMAIL, name="Maya Chen", subject="Wrong size delivered",
        summary="Hi! I ordered the linen shirt in M but received an L.\nCan you send the right size?",
        priority=TicketPriority.HIGH, source=TicketSource.CONTACT_FORM, order=sample_order(),
    )


def _order(order: Order) -> dict[str, Any]:
    return {"order": notifications.order_context(order)}


# Preview name -> (template kind, function that builds its data).
PREVIEWS: dict[str, tuple[str, Callable[[], dict[str, Any]]]] = {
    "verify_account": ("verify_account", lambda: {"name": "Maya", "verify_url": verify_url(make_token(PREVIEW_EMAIL))}),
    "confirm_order_email": (
        "confirm_order_email",
        lambda: {"order_number": "KO-1013", "verify_url": verify_url(make_token(PREVIEW_EMAIL, 1013))},
    ),
    "order_confirmation": ("order_confirmation", lambda: _order(sample_order())),
    "order_confirmation_cod": ("order_confirmation", lambda: _order(sample_order(cod=True))),
    "order_dispatched": (
        "order_dispatched",
        lambda: _order(o := sample_order()) | notifications.dispatch_context(o, OrderStatus.SHIPPED),
    ),
    "order_dispatched_partial": (
        "order_dispatched",
        lambda: _order(o := _with_note(sample_order(), "The tank top ships separately next week."))
        | notifications.dispatch_context(o, OrderStatus.PARTIALLY_SHIPPED),
    ),
    "order_update_out_for_delivery": (
        "order_update",
        lambda: _order(o := sample_order()) | notifications.update_context(o, OrderStatus.OUT_FOR_DELIVERY),
    ),
    "order_update_delivered": (
        "order_update",
        lambda: _order(o := sample_order()) | notifications.update_context(o, OrderStatus.DELIVERED),
    ),
    "order_update_delayed": (
        "order_update",
        lambda: _order(o := _with_note(sample_order(), "Severe weather has closed the Portland depot for a day."))
        | notifications.update_context(o, OrderStatus.DELAYED),
    ),
    "order_cancelled": (
        "order_cancelled",
        lambda: _order(o := sample_order()) | notifications.cancel_context(o, o.total_cents) | {"note": None},
    ),
    "order_cancelled_cod": (
        "order_cancelled",
        lambda: _order(o := sample_order(cod=True)) | notifications.cancel_context(o, 0) | {"note": "Cancelled at your request."},
    ),
    "return_approved": (
        "return_approved",
        lambda: _order((r := sample_return()).order) | {"ret": notifications.return_context(r), "note": None},
    ),
    "return_approved_exchange": (
        "return_approved",
        lambda: _order((r := sample_return(exchange=True)).order) | {"ret": notifications.return_context(r), "note": None},
    ),
    "return_rejected": (
        "return_rejected",
        lambda: _order((r := sample_return()).order)
        | {"ret": notifications.return_context(r), "note": "The tees arrived worn and without their tags (returns policy, rule 7)."},
    ),
    "refund_issued": (
        "refund_issued",
        lambda: _order((r := sample_return()).order)
        | {"ret": notifications.return_context(r), "refund": notifications.refund_context(r.order, 4800), "note": None},
    ),
    "ticket_alert": ("ticket_alert", lambda: notifications.ticket_context(_ticket())),
}


def render_preview(name: str) -> Rendered:
    kind, build = PREVIEWS[name]
    return render(kind, build())


def write_preview(name: str, out_dir: Path) -> Path:
    """Write <name>.html and <name>.txt; returns the HTML file's path."""
    rendered = render_preview(name)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{name}.html"
    html_path.write_text(rendered.html, encoding="utf-8")
    (out_dir / f"{name}.txt").write_text(f"Subject: {rendered.subject}\n\n{rendered.text}", encoding="utf-8")
    return html_path
