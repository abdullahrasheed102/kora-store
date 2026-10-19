#!/usr/bin/env bash
# Render's start command. Runs on every deploy AND every time the free instance wakes up.
# Both steps below are safe to repeat: they do nothing when there is nothing to do.
set -euo pipefail  # stop at the first failing step, so a broken migration never goes live

flask db upgrade      # apply new migrations (Alembic remembers which ones already ran)
flask images sync     # attach product photos listed in seed/image-manifest.json (idempotent)

# `exec` replaces this shell with gunicorn, so Render's stop signal reaches gunicorn directly
# and it can finish in-flight requests before shutting down.
exec gunicorn wsgi:app
