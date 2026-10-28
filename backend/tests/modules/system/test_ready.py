from fastapi.testclient import TestClient

from tests.database import SelectCounter


def test_ready_reports_available_database(
    db_client: TestClient, select_counter: SelectCounter
) -> None:
    response = db_client.get("/api/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert select_counter.count == 1


def test_ready_reports_unavailable_database(client: TestClient) -> None:
    response = client.get("/api/ready")

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "service.unavailable"
