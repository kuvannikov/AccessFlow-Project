import re

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from accessflow.app import create_app
from accessflow.core.config import Settings

PUBLIC_PATHS = {"/api/health", "/api/ready"}


def test_create_app_fails_without_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ACCESSFLOW_ENVIRONMENT", raising=False)

    with pytest.raises(ValidationError):
        create_app()


def test_api_requires_token_except_health_checks(settings: Settings) -> None:
    app = create_app(settings)
    # The OpenAPI document is the public list of operations; app.routes keeps
    # included routers as private wrappers.
    operations = [
        (method.upper(), path)
        for path, item in app.openapi()["paths"].items()
        if path not in PUBLIC_PATHS
        for method in item
    ]
    assert operations

    with TestClient(app) as client:
        for method, path in operations:
            # Authentication runs before path parameters are validated.
            response = client.request(method, re.sub(r"\{[^}]+\}", "0", path))
            assert response.status_code == 401, f"{method} {path}"
