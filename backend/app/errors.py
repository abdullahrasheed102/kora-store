"""Every error leaves the API as JSON: {"error": {"code": ..., "message": ...}}."""

from flask import Flask, jsonify
from flask.typing import ResponseReturnValue
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    """Raise from a route to return a specific error, e.g. APIError("out_of_stock", "...", 409)."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def error_response(code: str, message: str, status: int) -> ResponseReturnValue:
    return jsonify(error={"code": code, "message": message}), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)
    def handle_api_error(err: APIError) -> ResponseReturnValue:
        return error_response(err.code, err.message, err.status)

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException) -> ResponseReturnValue:
        # 404, 405, 400 from bad JSON, and 500 (Flask wraps unhandled exceptions in
        # InternalServerError, whose description is generic, so no internals leak).
        code = (err.name or "error").lower().replace(" ", "_")
        return error_response(code, err.description or "", err.code or 500)
