"""Email: the outbox, the providers that deliver it, templates, and address verification.

Named `mail` (not `email`) so it can never be confused with Python's built-in `email` module,
which the Mailpit sender uses.

    app/notifications.py   WHAT to send and WHEN (order paid, shipped, ticket created...)
    mail/outbox.py         writes outbox rows in the caller's transaction, sends them after commit
    mail/senders.py        HOW it leaves: log | mailpit | resend
    mail/render.py         Jinja templates -> subject, HTML and plain text
    mail/verification.py   signed "confirm your email" links, and the verified-address list
"""
