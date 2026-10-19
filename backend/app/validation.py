"""Turn request input (query strings and JSON bodies) into typed, validated objects with Pydantic."""

from typing import Any, TypeVar

from flask import request
from pydantic import BaseModel, ValidationError
from werkzeug.datastructures import MultiDict

from app.errors import APIError

Model = TypeVar("Model", bound=BaseModel)


def parse_query(model: type[Model], args: MultiDict[str, str]) -> Model:
    """Validate query-string arguments against a Pydantic model.

    Fields typed as lists (e.g. `size: list[str]`) collect every repeated value, so
    `?size=S&size=M` becomes ["S", "M"]. Empty values (`?q=`) count as "not given".
    """
    data: dict[str, object] = {}
    for name, field in model.model_fields.items():
        values = [value.strip() for value in args.getlist(name) if value.strip()]
        if not values:
            continue
        is_list = getattr(field.annotation, "__origin__", None) is list
        data[name] = values if is_list else values[0]
    return _validate(model, data)


def parse_json(model: type[Model]) -> Model:
    """Validate the request's JSON body against a Pydantic model.

    Requiring Content-Type: application/json is also a CSRF defence: a malicious site's
    HTML <form> can only send form-encoded or plain text bodies, and a cross-site fetch() with
    JSON triggers a CORS preflight that our API never approves.
    """
    if not request.is_json:
        raise APIError("unsupported_media_type", "Send the request body as JSON (Content-Type: application/json).", 415)
    data = request.get_json(silent=True)
    if data is None:
        raise APIError("invalid_json", "The request body is not valid JSON.", 400)
    return _validate(model, data)


def _validate(model: type[Model], data: Any) -> Model:
    try:
        return model.model_validate(data)
    except ValidationError as error:
        first = error.errors()[0]
        field = ".".join(str(part) for part in first["loc"]) or "body"
        raise APIError("validation_error", f"{field}: {first['msg']}", 400) from error
