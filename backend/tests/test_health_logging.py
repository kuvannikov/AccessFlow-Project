from io import StringIO

from sqlalchemy.exc import OperationalError

from app.db import get_session
from app.logging_config import logger
from app.main import app


def test_liveness_and_database_readiness(client):
    http, _ = client
    assert http.get("/api/health").json() == {"status": "alive"}
    response = http.get("/api/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert response.headers["X-Request-ID"]


def test_readiness_reports_database_failure_without_details(client):
    http, _ = client

    class BrokenSession:
        def execute(self, _):
            raise OperationalError("SELECT 1", {}, Exception("private-database-marker"))

    app.dependency_overrides[get_session] = lambda: BrokenSession()
    response = http.get("/api/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "private-database-marker" not in response.text


def test_unexpected_error_has_request_id_and_safe_logs(client, monkeypatch):
    http, make_token = client
    private_value = "private-token-marker"
    output_stream = StringIO()
    monkeypatch.setattr(logger.handlers[0], "stream", output_stream)

    def failed_session():
        raise RuntimeError(private_value)

    app.dependency_overrides[get_session] = failed_session
    response = http.get("/api/employees", headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 500
    identifier = response.headers["X-Request-ID"]
    assert response.json() == {"detail": "Внутренняя ошибка сервера", "request_id": identifier}
    output = output_stream.getvalue()
    assert f"request_id={identifier}" in output
    assert "unhandled_request_error" in output
    assert "RuntimeError" in output
    assert private_value not in output
    assert make_token() not in output
