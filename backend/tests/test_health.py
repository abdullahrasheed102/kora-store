"""Spec for GET /api/health and /api/health/live (app/api/health.py), and the security headers."""

from flask.testing import FlaskClient


def test_health_ok_when_database_reachable(client: FlaskClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "ok"}


def test_health_503_when_database_unreachable(unreachable_db_client: FlaskClient) -> None:
    response = unreachable_db_client.get("/api/health")

    assert response.status_code == 503
    # Exact match also proves no connection details (host, user, driver error) leak out.
    assert response.get_json() == {"status": "degraded", "database": "unavailable"}


def test_health_rejects_other_methods(client: FlaskClient) -> None:
    response = client.post("/api/health")

    assert response.status_code == 405
    assert response.get_json()["error"]["code"] == "method_not_allowed"


def test_liveness_never_touches_the_database(unreachable_db_client: FlaskClient) -> None:
    # Render's health check: it must stay green while Neon sleeps (and not wake it up).
    response = unreachable_db_client.get("/api/health/live")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_every_response_has_security_headers(client: FlaskClient) -> None:
    for response in (client.get("/api/health/live"), client.get("/api/no-such-route")):
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert response.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
        assert response.headers["Strict-Transport-Security"].startswith("max-age=63072000")
