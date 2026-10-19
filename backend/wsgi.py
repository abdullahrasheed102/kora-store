"""Entry point for servers: `flask run` (via .flaskenv) and `gunicorn wsgi:app` on Render."""

from app import create_app

app = create_app()
