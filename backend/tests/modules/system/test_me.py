import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.identity import SigningKey, access_claims, bearer


@pytest.fixture
def claims() -> dict[str, Any]:
    return access_claims(int(time.time()))


def test_returns_name_and_roles(
    auth_client: TestClient, signing_key: SigningKey, claims: dict[str, Any]
) -> None:
    response = auth_client.get("/api/me", headers=bearer(signing_key.sign(claims)))

    assert response.status_code == 200
    assert response.json() == {
        "displayName": "Анна Смирнова",
        "roles": ["HR", "default-roles-accessflow"],
    }


def test_user_without_roles_is_answered(
    auth_client: TestClient, signing_key: SigningKey, claims: dict[str, Any]
) -> None:
    del claims["realm_access"]

    response = auth_client.get("/api/me", headers=bearer(signing_key.sign(claims)))

    assert response.status_code == 200
    assert response.json() == {"displayName": "Анна Смирнова", "roles": []}


def test_requires_token(auth_client: TestClient) -> None:
    response = auth_client.get("/api/me")

    assert response.status_code == 401
    assert response.json()["code"] == "auth.invalid_token"
