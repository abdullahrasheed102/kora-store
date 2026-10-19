"""Gunicorn settings for production (Render). Gunicorn reads this file automatically.

Gunicorn is the WSGI server: it accepts HTTP connections and hands each request to Flask.
`flask run` is a development server (one request at a time, no protection against slow
clients), so it must never face the internet.
"""

import os

# Render tells us which port to listen on.
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# ONE worker process with several threads. Our requests mostly wait on the database, and threads
# share that waiting well. One process also keeps the in-memory rate-limit counters correct
# (config.py refuses memory:// with more workers) and fits the free instance's 512 MB.
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", "4"))

timeout = 30  # kill a request stuck for 30s (e.g. a hung database call) and restart the worker
graceful_timeout = 20  # on deploy/shutdown, let in-flight requests finish first
keepalive = 5

# Logs go to stdout/stderr, which Render shows in its Logs tab.
accesslog = "-"
errorlog = "-"
# The X-Forwarded-For chain is logged so we can check TRUSTED_PROXY_COUNT in production
# (see docs/guide/07-deployment.md, "Finding the real client IP").
access_log_format = '%(t)s "%(r)s" %(s)s %(b)sB %(M)sms xff="%({x-forwarded-for}i)s"'
