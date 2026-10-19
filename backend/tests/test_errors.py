"""The JSON error envelope wired up in app/errors.py."""

from flask import Flask
from flask.testing import FlaskClient

from app.errors import APIError


def test_unknown_route_returns_json_404(client: FlaskClient) -> None:
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_api_error_uses_its_code_and_status(app: Flask) -> None:
    def boom() -> None:
        raise APIError("out_of_stock", "Only 2 left.", 409)

    app.add_url_rule("/api/_boom", view_func=boom)
    response = app.test_client().get("/api/_boom")

    assert response.status_code == 409
    assert response.get_json() == {"error": {"code": "out_of_stock", "message": "Only 2 left."}}
