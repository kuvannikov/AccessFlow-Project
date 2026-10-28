from fastapi.testclient import TestClient


def test_ready_reports_unavailable_database(client: TestClient) -> None:
    response = client.get("/api/ready")

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "service.unavailable"
