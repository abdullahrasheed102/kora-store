"""Spec for GET /api/health (app/api/health.py)."""

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
