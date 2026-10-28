"""Request correlation, JSON integrity and private access logging."""

import json
import logging
import traceback
from time import perf_counter
from uuid import UUID, uuid4

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from accessflow.core.errors import internal_error_response, problem_response
from accessflow.core.logging import REQUEST_ID_ATTRIBUTE, http_logger, request_id_context

STANDARD_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"})


def _request_id(scope: Scope) -> str:
    values = [value for name, value in scope["headers"] if name.lower() == b"x-request-id"]
    if len(values) == 1:
        try:
            value = values[0].decode("ascii")
            parsed = UUID(value)
            if str(parsed) == value.lower():
                return str(parsed)
        except ValueError, UnicodeError:
            pass
    return str(uuid4())


def _is_json_media_type(content_type: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return (
        not media_type
        or media_type == "application/json"
        or (media_type.startswith("application/") and media_type.endswith("+json"))
    )


def _reject_json_constant(value: str) -> None:
    raise ValueError("Non-finite JSON number")


def _validate_unicode(value: object) -> None:
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            item.encode("utf-8")
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def _is_valid_json(body: bytes) -> bool:
    try:
        _validate_unicode(json.loads(body.decode("utf-8"), parse_constant=_reject_json_constant))
    except ValueError, UnicodeError, RecursionError:
        return False
    return True


def _error_origin(error: BaseException) -> str:
    frames = traceback.extract_tb(error.__traceback__)
    return f"{frames[-1].filename}:{frames[-1].lineno}" if frames else "-"


class RequestMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = _request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        context_token = request_id_context.set(request_id)
        started = perf_counter()
        status = 500
        response_started = False
        failure: Exception | None = None
        request = Request(scope, receive)

        async def send_response(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ]
                message = {**message, "headers": [*headers, (b"x-request-id", request_id.encode())]}
            await send(message)

        async def dispatch() -> None:
            if not _is_json_media_type(request.headers.get("content-type", "")):
                await self.app(scope, receive, send_response)
                return
            body = await request.body()
            if body and not _is_valid_json(body):
                response = problem_response(
                    request, 422, "request.invalid_body", "Invalid request body"
                )
                await response(scope, receive, send_response)
                return
            delivered = False

            async def replay_body() -> Message:
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

            await self.app(scope, replay_body, send_response)

        try:
            try:
                await dispatch()
            except Exception as error:
                failure = error
                if response_started:
                    # The protocol cannot replace a response that has already started.
                    setattr(error, REQUEST_ID_ATTRIBUTE, request_id)
                    raise
                await internal_error_response(request)(scope, receive, send_response)
        finally:
            method = scope["method"] if scope["method"] in STANDARD_METHODS else "OTHER"
            fields: dict[str, object] = {
                "request_id": request_id,
                "method": method,
                "route": getattr(scope.get("route"), "path", "unmatched"),
                "status": status,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
            }
            if failure is not None:
                # Type and location only: exception messages may carry submitted data.
                fields["error"] = type(failure).__qualname__
                fields["origin"] = _error_origin(failure)
            level = logging.ERROR if failure is not None or status >= 500 else logging.INFO
            http_logger.log(level, "request_completed", extra=fields)
            request_id_context.reset(context_token)
