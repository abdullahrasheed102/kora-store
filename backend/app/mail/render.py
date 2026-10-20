"""Turn a template name + data into a subject, an HTML body and a plain-text body.

Every email has both versions. The plain-text one is read by some people and mail apps, and
spam filters trust a message more when it has one.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import current_app
from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# The subject line of each email (a Jinja string). The keys are also the template file names:
# templates/<kind>.html and templates/<kind>.txt.
SUBJECTS: dict[str, str] = {
    "verify_account": "Confirm your email for Kora Outfitters",
    "confirm_order_email": "Confirm your email to get updates on order {{ order_number }}",
    "order_confirmation": "Your order {{ order.number }} is confirmed",
    "order_dispatched": "{{ 'Part of your order' if partial else 'Your order' }} {{ order.number }} is on its way",
    "order_update": "{{ update.subject }}",
    "order_cancelled": "Your order {{ order.number }} has been cancelled",
    "return_approved": "Your return for order {{ order.number }} is approved",
    "return_rejected": "About your return for order {{ order.number }}",
    "refund_issued": "Your refund for order {{ order.number }}",
    "ticket_alert": "New support ticket #{{ ticket.id }}: {{ ticket.subject }}",
}
KINDS = tuple(SUBJECTS)

# The store's design tokens (CLAUDE.md), repeated here because email can't load our CSS.
COLORS = {
    "ink": "#1f1b16",
    "background": "#f7f3ec",
    "card": "#fffdf9",
    "accent": "#b4532a",
    "sage": "#dfe6d6",
    "muted": "#6b6156",
    "border": "#e7dfd3",
}


def _environment(*, html: bool) -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        # HTML: escape every value, so a customer name like "<script>" shows as text.
        # Plain text has no markup to protect, and escaping would print "&amp;".
        autoescape=html,
        undefined=StrictUndefined,  # a typo in a template fails loudly instead of printing ""
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


_html_env = _environment(html=True)
_text_env = _environment(html=False)


@dataclass(frozen=True)
class Rendered:
    subject: str
    html: str
    text: str


def render(kind: str, context: dict[str, Any]) -> Rendered:
    if kind not in SUBJECTS:
        raise ValueError(f"Unknown email template {kind!r}; expected one of {', '.join(KINDS)}")
    values = {**base_context(), **context}
    # Collapse whitespace: a subject is one header line, and a newline in user input (a ticket
    # subject) must never be able to start a new header.
    subject = " ".join(_text_env.from_string(SUBJECTS[kind]).render(values).split())
    return Rendered(
        subject=subject,
        html=_html_env.get_template(f"{kind}.html").render(values, subject=subject),
        text=_text_env.get_template(f"{kind}.txt").render(values, subject=subject),
    )


def base_context() -> dict[str, Any]:
    return {
        "site_url": current_app.config["FRONTEND_URL"].rstrip("/"),
        "support_email": current_app.config["ADMIN_NOTIFY_EMAIL"],
        "colors": COLORS,
        "year": datetime.now().year,
    }
