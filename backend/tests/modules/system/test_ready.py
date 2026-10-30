import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection
from sqlalchemy.orm import sessionmaker
from testcontainers.community.postgres import PostgresContainer

from accessflow.app import create_app
from accessflow.modules.system import router
from tests.conftest import database_settings
from tests.database import SelectCounter


def test_ready_reports_available_database(
    db_client: TestClient, db_connection: Connection, select_counter: SelectCounter
) -> None:
    db_client.app.state.session_factory = sessionmaker(db_connection)  # type: ignore[attr-defined]

    response = db_client.get("/api/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert select_counter.count == 1


def test_ready_reports_unavailable_database(client: TestClient) -> None:
    response = client.get("/api/ready")

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "service.unavailable"


def test_ready_answers_while_database_is_frozen(
    postgres: PostgresContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(router, "READINESS_TIMEOUT_SECONDS", 1)
    container = postgres.get_wrapped_container()
    assert container is not None
    with TestClient(create_app(database_settings(postgres, "accessflow_app"))) as client:
        assert client.get("/api/ready").status_code == 200
        container.pause()
        try:
            started = time.perf_counter()
            frozen = client.get("/api/ready")
            elapsed = time.perf_counter() - started
            health = client.get("/api/health")
        finally:
            container.unpause()

        assert frozen.status_code == 503
        assert elapsed < 2
        assert health.status_code == 200
        assert client.get("/api/ready").status_code == 200
