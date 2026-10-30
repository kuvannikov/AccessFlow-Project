import logging
import re
from unittest.mock import Mock

from fastapi.testclient import TestClient

from accessflow.app import create_app
from accessflow.core.config import Settings
from accessflow.core.logging import ServerErrorFilter

PUBLIC_PATHS = {"/api/health", "/api/ready"}


def test_server_logs_are_filtered(settings: Settings) -> None:
    create_app(settings)

    filters = logging.getLogger("uvicorn.error").filters
    assert any(isinstance(item, ServerErrorFilter) for item in filters)


def test_engine_is_disposed_on_shutdown(settings: Settings) -> None:
    app = create_app(settings)
    app.state.engine.dispose = dispose = Mock()

    with TestClient(app):
        dispose.assert_not_called()

    dispose.assert_called_once_with()


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
