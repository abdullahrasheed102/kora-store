"""The outbox: write emails in the caller's transaction, send them after it commits.

    1. enqueue()        adds an email_outbox row in the SAME transaction as the change that
                        caused it. Rolled back together, committed together.
    2. after commit     the session hook below hands the new row ids to a sender, so the email
                        goes out within seconds, without making the shopper wait for it.
    3. process_outbox() claims due rows, applies the abuse rules (blocked domains, daily caps),
                        sends, and records the result. A failure is retried later with backoff.
    4. every 5 minutes  GitHub Actions calls POST /api/email/outbox/process, which runs step 3
                        for anything still pending (a crash, a provider outage, a deferred email).
"""

import logging
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import Flask, current_app, has_app_context
from sqlalchemy import and_, event, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.extensions import db
from app.mail.render import render
from app.mail.senders import EmailSender, OutgoingEmail, SendError, get_sender
from app.models import EmailOutbox, EmailStatus, normalize_email

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 6
# Wait after the 1st, 2nd, ... failed attempt. The retry job runs every 5 minutes, so the short
# waits really mean "on the next run". Total: about 5 hours before we give up.
RETRY_DELAYS = [timedelta(minutes=m) for m in (1, 5, 15, 60, 240)]
LEASE = timedelta(minutes=2)  # a "sending" row belongs to its sender for this long
BATCH_SIZE = 50
# Any number works, as long as nothing else in the app uses the same advisory lock id.
CLAIM_LOCK_ID = 80_801

# Reserved for documentation and testing (RFC 2606 and RFC 6761): no real person reads these.
# All 12 demo orders use @example.com, so they can never trigger a real email.
BLOCKED_DOMAINS = {"example.com", "example.net", "example.org", "kora.test"}
BLOCKED_TLDS = {"test", "example", "invalid", "localhost"}

# Where enqueue() leaves the ids of new rows for the after-commit hook (per session).
NEW_IDS = "kora_outbox_new_ids"


def is_blocked(email: str) -> bool:
    domain = normalize_email(email).rpartition("@")[2]
    return (
        domain in BLOCKED_DOMAINS
        or any(domain.endswith("." + blocked) for blocked in BLOCKED_DOMAINS)
        or domain.rpartition(".")[2] in BLOCKED_TLDS
    )


def utc_now() -> datetime:
    return datetime.now(UTC)


# --- 1. writing ---------------------------------------------------------------------------------


def enqueue(
    session: Session,
    *,
    key: str,
    kind: str,
    to: str,
    context: dict[str, Any],
    reply_to: str | None = None,
    order_id: int | None = None,
    suppressed_reason: str | None = None,
) -> int | None:
    """Add one email to the outbox, inside the caller's transaction (the caller commits).

    Returns the new row id, or None if an email with this idempotency key already exists.
    A suppressed email is still recorded (for the audit trail), but never sent.
    """
    to = normalize_email(to)
    if suppressed_reason is None and is_blocked(to):
        suppressed_reason = "blocked_domain"
    rendered = render(kind, context)
    status = EmailStatus.SUPPRESSED if suppressed_reason else EmailStatus.PENDING

    # INSERT ... ON CONFLICT DO NOTHING: layer 1 of idempotency. If the same trigger runs twice,
    # the database itself refuses the duplicate, even when two requests race each other.
    new_id = session.execute(
        insert(EmailOutbox)
        .values(
            idempotency_key=key,
            kind=kind,
            to_email=to,
            reply_to=reply_to,
            subject=rendered.subject,
            html_body=rendered.html,
            text_body=rendered.text,
            status=status,
            suppressed_reason=suppressed_reason,
            order_id=order_id,
        )
        .on_conflict_do_nothing(index_elements=["idempotency_key"])
        .returning(EmailOutbox.id)
    ).scalar_one_or_none()

    if new_id is not None and status is EmailStatus.PENDING:
        session.info.setdefault(NEW_IDS, []).append(new_id)
    return new_id


# --- 2. sending right after the commit ------------------------------------------------------------


@event.listens_for(Session, "after_commit")
def _send_after_commit(session: Session) -> None:
    """The transaction that wrote these rows is committed, so the emails are now real promises."""
    ids = session.info.pop(NEW_IDS, None)
    if not ids:
        return
    mark_maybe_due()
    if not has_app_context():
        return  # e.g. a script without the app: the scheduled job will send them
    app: Flask = current_app._get_current_object()  # type: ignore[attr-defined]
    if app.config["EMAIL_SEND_IN_BACKGROUND"]:
        # A separate thread, so the HTTP response doesn't wait for the email provider. Not a
        # daemon thread: on shutdown Python waits for it (at most one provider timeout).
        threading.Thread(target=_send_ids, args=(app, ids), name="outbox-after-commit").start()
    else:
        _send_ids(app, ids)


@event.listens_for(Session, "after_rollback")
def _forget_after_rollback(session: Session) -> None:
    # The rows are gone with the transaction, so there is nothing to send.
    session.info.pop(NEW_IDS, None)


def _send_ids(app: Flask, ids: list[int]) -> None:
    # A fresh app context gives this work its own database session. We must not reuse the
    # session that is in the middle of committing.
    with app.app_context():
        try:
            process_outbox(db.session, ids=ids)
        except Exception:
            # Never break the request that caused the email. The rows are still pending, so the
            # scheduled job will pick them up.
            log.exception("Sending outbox emails %s after commit failed", ids)
            db.session.rollback()


# --- 3. processing --------------------------------------------------------------------------------


@dataclass
class ProcessReport:
    sent: int = 0
    retrying: int = 0
    failed: int = 0
    suppressed: int = 0
    deferred: int = 0  # over the global daily cap: moved to tomorrow

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def process_outbox(session: Session, *, ids: list[int] | None = None, now: datetime | None = None) -> ProcessReport:
    """Send due emails: only `ids` (right after a commit), or everything due (the retry job)."""
    now = now or utc_now()
    report = ProcessReport()
    claimed = _claim(session, now, ids, report)
    if not claimed:
        return report
    sender = get_sender()
    for row in claimed:
        _deliver(session, sender, row, report)
    return report


def _claim(session: Session, now: datetime, ids: list[int] | None, report: ProcessReport) -> list[EmailOutbox]:
    """Pick due rows and mark them "sending", deciding the caps on the way. Then commit.

    The commit matters: we never hold row locks while waiting on the network (the same rule as
    refunds in app/admin.py). The lease (locked_until) protects the row instead.
    """
    # One claimer at a time across all threads and processes: counting today's emails and then
    # claiming more must not interleave, or two claimers could both squeeze under the cap.
    session.execute(select(func.pg_advisory_xact_lock(CLAIM_LOCK_ID)))

    due = or_(
        and_(EmailOutbox.status == EmailStatus.PENDING, EmailOutbox.next_attempt_at <= now),
        # A sender crashed mid-send (or the server restarted): its lease ran out, take it over.
        and_(EmailOutbox.status == EmailStatus.SENDING, EmailOutbox.locked_until < now),
    )
    stmt = select(EmailOutbox).where(due).order_by(EmailOutbox.id).limit(BATCH_SIZE).with_for_update(skip_locked=True)
    if ids is not None:
        stmt = stmt.where(EmailOutbox.id.in_(ids))
    rows = list(session.scalars(stmt))
    if not rows:
        session.commit()
        return []

    config = current_app.config
    day_start = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    used_today = (EmailOutbox.status.in_([EmailStatus.SENT, EmailStatus.SENDING]), EmailOutbox.last_attempt_at >= day_start)
    sent_today = session.scalar(select(func.count()).where(*used_today)) or 0
    per_recipient: dict[str, int] = dict(
        session.execute(  # type: ignore[arg-type]
            select(EmailOutbox.to_email, func.count())
            .where(*used_today, EmailOutbox.to_email.in_({row.to_email for row in rows}))
            .group_by(EmailOutbox.to_email)
        ).all()
    )
    admin_address = normalize_email(config["ADMIN_NOTIFY_EMAIL"] or "")

    claimed = []
    for row in rows:
        if is_blocked(row.to_email):  # checked again here in case a row was written by other code
            _suppress(row, "blocked_domain", report)
        elif row.to_email != admin_address and per_recipient.get(row.to_email, 0) >= config["EMAIL_RECIPIENT_DAILY_CAP"]:
            # Many emails to one stranger in a day looks like abuse: drop, don't postpone.
            _suppress(row, "recipient_daily_cap", report)
        elif sent_today >= config["EMAIL_DAILY_CAP"]:
            # Our whole budget is used up. That's not the customer's fault: send it tomorrow.
            row.next_attempt_at = day_start + timedelta(days=1)
            report.deferred += 1
        else:
            row.status = EmailStatus.SENDING
            row.attempts += 1
            row.last_attempt_at = now
            row.locked_until = now + LEASE
            sent_today += 1
            per_recipient[row.to_email] = per_recipient.get(row.to_email, 0) + 1
            claimed.append(row)
    session.commit()  # also releases the advisory lock (it was taken "for this transaction")
    return claimed


def _suppress(row: EmailOutbox, reason: str, report: ProcessReport) -> None:
    row.status = EmailStatus.SUPPRESSED
    row.suppressed_reason = reason
    report.suppressed += 1


def _deliver(session: Session, sender: EmailSender, row: EmailOutbox, report: ProcessReport) -> None:
    config = current_app.config
    email = OutgoingEmail(
        to=row.to_email,
        sender=config["EMAIL_FROM"],
        reply_to=row.reply_to,
        subject=row.subject,
        html=row.html_body,
        text=row.text_body,
        idempotency_key=row.idempotency_key,
    )
    try:
        message_id = sender.send(email)
    except Exception as error:
        retryable = error.retryable if isinstance(error, SendError) else True
        _record_failure(row, error, retryable, report)
    else:
        row.status = EmailStatus.SENT
        row.sent_at = utc_now()
        row.provider_message_id = message_id[:100]
        row.locked_until = None
        row.last_error = None
        report.sent += 1
    session.commit()  # one commit per email: a later failure can't undo an earlier success


def _record_failure(row: EmailOutbox, error: Exception, retryable: bool, report: ProcessReport) -> None:
    log.warning("Email %s (%s) attempt %s failed: %s", row.id, row.kind, row.attempts, error)
    row.last_error = str(error)[:1000]
    row.locked_until = None
    if retryable and row.attempts < MAX_ATTEMPTS:
        row.status = EmailStatus.PENDING
        # Counted from when this attempt started, so the schedule doesn't drift.
        row.next_attempt_at = row.last_attempt_at + RETRY_DELAYS[min(row.attempts, len(RETRY_DELAYS)) - 1]
        report.retrying += 1
    else:
        row.status = EmailStatus.FAILED
        report.failed += 1


# --- 4. the scheduled retry job -----------------------------------------------------------------------

# "Might there be something to send?" Kept in memory so the 5-minute job can skip the database
# when the answer is clearly no. That lets Neon's free compute go to sleep between orders
# instead of being woken every 5 minutes. True at start-up, so after a restart (or a crash that
# lost an after-commit send) the first run always checks the database.
_maybe_due = True


def mark_maybe_due() -> None:
    global _maybe_due
    _maybe_due = True


def run_scheduled(session: Session, *, force: bool = False) -> dict[str, Any]:
    """The retry job. Skips the database entirely when nothing can be due."""
    global _maybe_due
    if not (_maybe_due or force):
        return {"skipped": True}
    # Clear the flag BEFORE looking, so an email enqueued while we work sets it again.
    _maybe_due = False
    report = process_outbox(session)
    still_waiting = session.scalar(
        select(func.count()).where(EmailOutbox.status.in_([EmailStatus.PENDING, EmailStatus.SENDING]))
    )
    if still_waiting:
        _maybe_due = True  # retries or deferred emails are scheduled for later
    return {"skipped": False, **report.as_dict(), "waiting": still_waiting}
