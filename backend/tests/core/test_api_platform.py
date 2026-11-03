import asyncio
import io
import json
import logging
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.responses import StreamingResponse
from starlette.types import Message, Scope

from accessflow.app import create_app
from accessflow.core.config import Settings
from accessflow.core.errors import DomainError, ProblemDefinition
from accessflow.core.logging import HttpFormatter, ServerErrorFilter, http_logger
from accessflow.core.middleware import MAX_BODY_BYTES


class SubmittedData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(alias="displayName", min_length=2)

    @field_validator("display_name")
    @classmethod
    def reject_canary_value(cls, value: str) -> str:
        if value.startswith("canary"):
            raise ValueError(value)
        return value


class ConflictError(DomainError):
    pass


class UnknownError(DomainError):
    pass


@pytest.fixture
def platform_app(settings: Settings) -> FastAPI:
    app = create_app(settings)
    app.state.error_registry.register(
        ConflictError, ProblemDefinition(409, "example.conflict", "Conflict")
    )

    @app.post("/test/body")
    def submit(data: SubmittedData) -> dict[str, str]:
        return {"displayName": data.display_name}

    @app.get("/test/http/{status}")
    def http_error(status: int) -> None:
        raise HTTPException(status, detail="canary-http-detail", headers={"Retry-After": "3"})

    @app.get("/test/domain")
    def domain_error() -> None:
        raise ConflictError("canary-domain-message")

    @app.get("/test/unknown")
    def unknown_error() -> None:
        raise UnknownError("canary-unknown-message")

    @app.get("/test/crash/{value}")
    def crash(value: str) -> None:
        raise RuntimeError(value)

    @app.get("/test/request-id")
    async def request_id(request: Request) -> dict[str, str]:
        await asyncio.sleep(0)
        return {"requestId": request.state.request_id}

    @app.get("/test/stream")
    def stream() -> StreamingResponse:
        def chunks() -> Iterator[bytes]:
            yield b"ok"
            raise RuntimeError("canary-stream-error")

        return StreamingResponse(chunks())

    return app


@pytest.fixture
def platform_client(platform_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(platform_app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def http_output() -> Iterator[io.StringIO]:
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(HttpFormatter())
    http_logger.addHandler(handler)
    try:
        yield output
    finally:
        http_logger.removeHandler(handler)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 405, 409, 422, 429, 503])
def test_http_errors_are_safe(platform_client: TestClient, status: int) -> None:
    response = platform_client.get(f"/test/http/{status}")
    body = response.json()
    assert response.status_code == status
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["retry-after"] == "3"
    assert body["status"] == status
    assert body["type"] == f"/problems/{body['code']}"
    assert body["requestId"] == response.headers["x-request-id"]
    assert "canary" not in response.text


@pytest.mark.parametrize("path", ["/test/unknown", "/test/crash/canary-error", "/test/http/500"])
def test_internal_errors_have_minimal_body(
    platform_client: TestClient, http_output: io.StringIO, path: str
) -> None:
    response = platform_client.get(path, params={"search": "canary-search"})
    assert response.status_code == 500
    assert response.json() == {"code": "internal", "requestId": response.headers["x-request-id"]}
    assert "canary" not in response.text + http_output.getvalue()


def test_unhandled_error_log_names_type_and_origin(
    platform_client: TestClient, http_output: io.StringIO
) -> None:
    platform_client.get("/test/crash/canary-error")
    log = http_output.getvalue()
    assert 'error="RuntimeError"' in log
    assert f"origin={json.dumps(__file__)[:-1]}:" in log
    assert "canary-error" not in log


def test_domain_registry(platform_client: TestClient) -> None:
    response = platform_client.get("/test/domain")
    assert response.status_code == 409
    assert response.json()["code"] == "example.conflict"
    assert "canary" not in response.text


def test_registry_rejects_duplicate_registration(platform_app: FastAPI) -> None:
    with pytest.raises(ValueError, match="already registered"):
        platform_app.state.error_registry.register(
            ConflictError, ProblemDefinition(409, "example.other", "Other")
        )


@pytest.mark.parametrize(
    "body",
    [
        b'{"displayName":',
        b'{"displayName":"\xff"}',
        b'{"displayName":"\\ud800"}',
        b'{"\\udfff":"value"}',
    ],
)
@pytest.mark.parametrize("content_type", ["application/json", "application/problem+json", None])
def test_invalid_json_and_unicode(
    platform_client: TestClient, http_output: io.StringIO, body: bytes, content_type: str | None
) -> None:
    headers = {"content-type": content_type} if content_type else {}
    response = platform_client.post("/test/body", content=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["code"] == "request.invalid_body"
    assert "displayName" not in response.text + http_output.getvalue()


@pytest.mark.parametrize(
    "data",
    [
        {"displayName": "canary-validator-message"},
        {"displayName": 123, "canary-extra-field": "canary-value"},
        {},
    ],
)
def test_validation_does_not_echo_input(
    platform_client: TestClient, http_output: io.StringIO, data: dict[str, object]
) -> None:
    response = platform_client.post(
        "/test/body?search=canary-query",
        json=data,
        headers={"authorization": "Bearer canary-header"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation.failed"
    assert {"field": "displayName", "code": "invalid"} in body["errors"]
    assert "canary" not in response.text + http_output.getvalue()
    assert "input" not in response.text
    assert "ctx" not in response.text


def test_valid_body_still_reaches_endpoint(platform_client: TestClient) -> None:
    response = platform_client.post("/test/body", json={"displayName": "Анна"})
    assert response.status_code == 200
    assert response.json() == {"displayName": "Анна"}


@pytest.mark.parametrize(
    "value", [None, "invalid", "", "a" * 100, "00000000000000000000000000000000"]
)
def test_request_id_is_generated(platform_client: TestClient, value: str | None) -> None:
    headers = {"x-request-id": value} if value is not None else {}
    response = platform_client.get("/api/health", headers=headers)
    assert str(UUID(response.headers["x-request-id"])) == response.headers["x-request-id"]


@pytest.mark.parametrize("form", ["hex", "braces", "urn"])
def test_non_canonical_request_id_is_replaced(platform_client: TestClient, form: str) -> None:
    original = uuid4()
    value = {"hex": original.hex, "braces": f"{{{original}}}", "urn": original.urn}[form]
    response = platform_client.get("/api/health", headers={"x-request-id": value})
    assert response.headers["x-request-id"] != str(original)


def test_uppercase_request_id_is_normalized(platform_client: TestClient) -> None:
    original = uuid4()
    response = platform_client.get("/api/health", headers={"x-request-id": str(original).upper()})
    assert response.headers["x-request-id"] == str(original)


def test_valid_request_id_is_used_everywhere(
    platform_client: TestClient, http_output: io.StringIO
) -> None:
    request_id = str(uuid4())
    response = platform_client.get("/test/crash/canary", headers={"x-request-id": request_id})
    assert response.headers["x-request-id"] == response.json()["requestId"] == request_id
    assert f'request_id="{request_id}"' in http_output.getvalue()
    assert 'route="/test/crash/{value}"' in http_output.getvalue()
    assert "canary" not in http_output.getvalue()


def test_duplicate_request_ids_are_replaced(platform_client: TestClient) -> None:
    first, second = str(uuid4()), str(uuid4())
    response = platform_client.get(
        "/api/health", headers=[("x-request-id", first), ("x-request-id", second)]
    )
    assert response.headers["x-request-id"] not in {first, second}


def test_unmatched_paths_and_methods_are_safe(
    platform_client: TestClient, http_output: io.StringIO
) -> None:
    assert platform_client.get("/canary-path?q=canary-query").status_code == 404
    assert platform_client.post("/api/health").status_code == 405
    lines = http_output.getvalue().splitlines()
    assert len(lines) == 2
    assert 'route="unmatched"' in lines[0]
    assert "canary" not in http_output.getvalue()
    assert logging.getLogger("uvicorn.access").disabled


def test_request_ids_isolated_between_concurrent_requests(platform_app: FastAPI) -> None:
    async def run() -> None:
        async def invoke(request_id: str) -> None:
            messages: list[Message] = []
            scope: Scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/test/request-id",
                "raw_path": b"/test/request-id",
                "query_string": b"",
                "headers": [(b"x-request-id", request_id.encode())],
                "server": ("test", 80),
                "client": ("test", 1),
            }

            async def receive() -> Message:
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message: Message) -> None:
                messages.append(message)

            await platform_app(scope, receive, send)
            body = b"".join(message.get("body", b"") for message in messages)
            assert json.loads(body) == {"requestId": request_id}

        await asyncio.gather(*(invoke(str(uuid4())) for _ in range(10)))

    asyncio.run(run())


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity", "1e400", "-1e400", "1E999"])
def test_non_finite_numbers_are_not_json(platform_client: TestClient, constant: str) -> None:
    response = platform_client.post(
        "/test/body",
        content='{"displayName":' + constant + "}",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "request.invalid_body"


def json_body_of_size(size: int) -> bytes:
    overhead = len(b'{"displayName":""}')
    return b'{"displayName":"' + b"a" * (size - overhead) + b'"}'


def test_body_at_the_limit_is_accepted(platform_client: TestClient) -> None:
    response = platform_client.post(
        "/test/body",
        content=json_body_of_size(MAX_BODY_BYTES),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 200


@pytest.mark.parametrize("content_type", ["application/json", "text/plain", None])
def test_declared_oversized_body_is_rejected(
    platform_client: TestClient, content_type: str | None
) -> None:
    headers = {"content-type": content_type} if content_type else {}
    response = platform_client.post(
        "/test/body", content=json_body_of_size(MAX_BODY_BYTES + 1), headers=headers
    )
    assert response.status_code == 413
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "request.too_large"


@pytest.mark.parametrize(
    "content_type", ["application/json", "text/plain", "application/x-www-form-urlencoded"]
)
def test_oversized_streamed_body_is_rejected(
    platform_client: TestClient, content_type: str
) -> None:
    def chunks() -> Iterator[bytes]:
        yield from (b"a" * 1024 for _ in range(MAX_BODY_BYTES // 1024 + 1))

    response = platform_client.post(
        "/test/body", content=chunks(), headers={"content-type": content_type}
    )
    assert response.status_code == 413
    assert response.json()["code"] == "request.too_large"


def test_non_json_body_is_left_to_endpoint_validation(platform_client: TestClient) -> None:
    response = platform_client.post(
        "/test/body", content=b"not json", headers={"content-type": "text/plain"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation.failed"


def test_late_stream_failure_is_correlated(
    platform_client: TestClient, http_output: io.StringIO
) -> None:
    request_id = str(uuid4())
    with (
        pytest.raises(RuntimeError, match="canary-stream-error") as caught,
        TestClient(platform_client.app) as raising_client,
    ):
        raising_client.get("/test/stream", headers={"x-request-id": request_id})
    assert caught.value.__dict__["_accessflow_request_id"] == request_id
    assert f'request_id="{request_id}"' in http_output.getvalue()
    assert 'level="ERROR"' in http_output.getvalue()
    assert "status=200" in http_output.getvalue()
    assert "canary" not in http_output.getvalue()


def test_server_exception_log_is_safe() -> None:
    error = RuntimeError("canary-error")
    request_id = str(uuid4())
    error.__dict__["_accessflow_request_id"] = request_id
    record = logging.LogRecord(
        "uvicorn.error",
        logging.ERROR,
        __file__,
        1,
        "canary-message",
        (),
        (RuntimeError, error, None),
    )
    record.exc_text = "canary-cached-traceback"
    assert ServerErrorFilter().filter(record)
    result = logging.Formatter().format(record)
    assert request_id in result
    assert "canary" not in result
    assert "\n" not in result
