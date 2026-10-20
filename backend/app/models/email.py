"""The email outbox, and the addresses we're allowed to send customer emails to."""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.types import CreatedAt, EmailStatus, IntPK, enum_column


class EmailOutbox(db.Model):
    """One email we have promised to send (the outbox pattern).

    Rows are written in the SAME transaction as the change that causes them (an order paid, a
    status changed). So if that change is rolled back, the email disappears with it, and once it
    is committed the email can't be lost: a sender delivers it after the commit, and a scheduled
    job retries anything still pending. The full message is rendered when the row is written, so
    a retry hours later sends exactly what was true at the moment of the change.
    """

    __tablename__ = "email_outbox"
    __table_args__ = (
        # The sender's main query: "pending rows that are due now".
        Index("ix_email_outbox_status_next_attempt_at", "status", "next_attempt_at"),
        # The daily caps count today's sends, overall and per recipient.
        Index("ix_email_outbox_to_email_last_attempt_at", "to_email", "last_attempt_at"),
    )

    id: Mapped[IntPK]
    # Unique: the same trigger running twice (a retried webhook, a double click) inserts nothing
    # the second time. Also sent to Resend as its Idempotency-Key header.
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    kind: Mapped[str] = mapped_column(String(40))  # template name, e.g. "order_confirmation"
    to_email: Mapped[str] = mapped_column(String(254))
    reply_to: Mapped[str | None] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(200))
    html_body: Mapped[str] = mapped_column(Text)
    text_body: Mapped[str] = mapped_column(Text)

    status: Mapped[EmailStatus] = mapped_column(
        enum_column(EmailStatus, "email_status"),
        default=EmailStatus.PENDING,
        server_default=EmailStatus.PENDING.value,
    )
    suppressed_reason: Mapped[str | None] = mapped_column(String(40))
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    last_attempt_at: Mapped[datetime | None]
    # A lease: a row in "sending" belongs to one sender until this time. If that sender crashes,
    # the lease runs out and the row can be claimed again.
    locked_until: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(Text)
    provider_message_id: Mapped[str | None] = mapped_column(String(100))

    # SET NULL: the email history stays even if a (test) order is deleted.
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[CreatedAt]
    sent_at: Mapped[datetime | None]

    def __repr__(self) -> str:
        return f"<EmailOutbox {self.kind} to {self.to_email} ({self.status})>"


class VerifiedEmail(db.Model):
    """An address whose owner proved they read it, by clicking a link we sent there.

    Anyone can type any address at checkout, so without this the store could be used to send
    mail to strangers. Customer emails go only to addresses listed here.
    """

    __tablename__ = "verified_emails"

    email: Mapped[str] = mapped_column(String(254), primary_key=True)  # stored lowercase
    verified_at: Mapped[CreatedAt]

    def __repr__(self) -> str:
        return f"<VerifiedEmail {self.email}>"
