"""Safe public errors. Exception messages and submitted values stay private."""

from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

PROBLEM_MEDIA_TYPE = "application/problem+json"

HTTP_ERROR_CODES: Mapping[int, str] = {
    401: "auth.invalid_token",
    403: "auth.forbidden",
    404: "request.not_found",
    405: "request.method_not_allowed",
    422: "validation.failed",
    503: "service.unavailable",
}


class DomainError(Exception):
    """Base for business failures; public descriptions live in the registry."""


@dataclass(frozen=True)
class ProblemDefinition:
    status: int
    code: str
    title: str

    def __post_init__(self) -> None:
        if not 400 <= self.status < 500 and self.status != 503:
            raise ValueError("Public errors must use a client error status or 503")


class ErrorRegistry:
    """Explicit mapping from exception types to reviewed public descriptions."""

    def __init__(self) -> None:
        self._definitions: dict[type[DomainError], ProblemDefinition] = {}

    def register(self, error: type[DomainError], definition: ProblemDefinition) -> None:
        if error in self._definitions:
            raise ValueError("Error type already registered")
        self._definitions[error] = definition

    def resolve(self, error: DomainError) -> ProblemDefinition | None:
        return self._definitions.get(type(error))


def problem_response(
    request: Request,
    status: int,
    code: str,
    title: str,
    *,
    errors: list[dict[str, str]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    content: dict[str, object] = {
        "type": f"/problems/{code}",
        "title": title,
        "status": status,
        "code": code,
        "requestId": request.state.request_id,
    }
    if errors:
        content["errors"] = errors
    return JSONResponse(content, status_code=status, media_type=PROBLEM_MEDIA_TYPE, headers=headers)


def internal_error_response(request: Request) -> JSONResponse:
    content = {"code": "internal", "requestId": request.state.request_id}
    return JSONResponse(content, status_code=500, media_type=PROBLEM_MEDIA_TYPE)


async def http_error_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, HTTPException):
        raise TypeError("Unexpected exception handler argument")
    status = error.status_code
    if status >= 500 and status != 503:
        return internal_error_response(request)
    code = HTTP_ERROR_CODES.get(status, "request.rejected")
    title = HTTPStatus(status).phrase if status in HTTPStatus else "Request rejected"
    # Preserve protocol headers such as Allow and WWW-Authenticate, never detail.
    return problem_response(request, status, code, title, headers=error.headers)


def _declared_fields(request: Request) -> set[str]:
    fields: set[str] = set()
    dependant = getattr(request.scope.get("route"), "dependant", None)
    if dependant is None:
        return fields
    for parameter in (*dependant.body_params, *dependant.path_params, *dependant.query_params):
        fields.add(parameter.alias)
        model_fields = getattr(parameter.field_info.annotation, "model_fields", {})
        fields.update(field.alias or name for name, field in model_fields.items())
    return fields


async def validation_error_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, RequestValidationError):
        raise TypeError("Unexpected exception handler argument")
    if any(item["type"] == "json_invalid" for item in error.errors()):
        return problem_response(request, 422, "request.invalid_body", "Invalid request body")
    # Locations and messages can contain submitted dictionary keys or validator text.
    # Expose only declared top-level aliases, never arbitrary location components.
    fields = _declared_fields(request)
    errors: list[dict[str, str]] = []
    for item in error.errors():
        entry = {"code": "invalid"}
        location = item.get("loc", ())
        if len(location) > 1 and location[1] in fields:
            entry["field"] = location[1]
        if entry not in errors:
            errors.append(entry)
    return problem_response(request, 422, "validation.failed", "Validation failed", errors=errors)


async def domain_error_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, DomainError):
        raise TypeError("Unexpected exception handler argument")
    registry: ErrorRegistry = request.app.state.error_registry
    definition = registry.resolve(error)
    if definition is None:
        return internal_error_response(request)
    return problem_response(request, definition.status, definition.code, definition.title)


def install_error_handlers(app: FastAPI) -> None:
    app.state.error_registry = ErrorRegistry()
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(DomainError, domain_error_handler)
