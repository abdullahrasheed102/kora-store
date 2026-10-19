"""Endpoints for the AI support agent, protected by the X-Agent-Key header (phase 8)."""

from flask import Blueprint

bp = Blueprint("agent", __name__)
