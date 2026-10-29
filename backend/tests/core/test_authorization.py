import time
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from accessflow.core.config import Settings
from tests.authorization import protected_client
from tests.identity import SigningKey, access_claims, bearer, with_jwks_url


@pytest.fixture
def claims() -> dict[str, Any]:
    return access_claims(int(time.time()))


@pytest.fixture
def client(auth_settings: Settings) -> Iterator[TestClient]:
    with protected_client(auth_settings) as test_client:
        yield test_client


def test_role_holder_is_admitted(
    client: TestClient, signing_key: SigningKey, claims: dict[str, Any]
) -> None:
    response = client.get("/test/hr", headers=bearer(signing_key.sign(claims)))

    assert response.status_code == 200
    assert response.json() == {"subject": claims["sub"]}


@pytest.mark.parametrize(
    "roles",
    [[], ["default-roles-accessflow"], ["hr"], ["HR "], ["HR-admin"]],
    ids=["none", "default only", "lowercase", "trailing space", "prefix"],
)
def test_missing_role_is_forbidden(
    client: TestClient, signing_key: SigningKey, claims: dict[str, Any], roles: list[str]
) -> None:
    claims["realm_access"] = {"roles": roles}

    response = client.get("/test/hr", headers=bearer(signing_key.sign(claims)))

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "auth.forbidden"


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer"}, {"Authorization": "Basic dXNlcjpwYXNz"}],
    ids=["no header", "no token", "other scheme"],
)
def test_missing_token_is_unauthorized(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get("/test/hr", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["code"] == "auth.invalid_token"


def test_invalid_token_is_unauthorized(
    client: TestClient, signing_key: SigningKey, claims: dict[str, Any]
) -> None:
    claims["aud"] = "account"

    response = client.get("/test/hr", headers=bearer(signing_key.sign(claims)))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Bearer error="invalid_token"'
    assert response.json()["code"] == "auth.invalid_token"


def test_malformed_roles_are_unauthorized(
    client: TestClient, signing_key: SigningKey, claims: dict[str, Any]
) -> None:
    claims["realm_access"] = {"roles": "HR"}

    response = client.get("/test/hr", headers=bearer(signing_key.sign(claims)))

    assert response.status_code == 401
    assert response.json()["code"] == "auth.invalid_token"


def test_unreachable_identity_provider_is_unavailable(
    settings: Settings, closed_port: int, signing_key: SigningKey, claims: dict[str, Any]
) -> None:
    unreachable = with_jwks_url(settings, f"http://127.0.0.1:{closed_port}/certs")

    with protected_client(unreachable) as client:
        response = client.get("/test/hr", headers=bearer(signing_key.sign(claims)))

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["code"] == "auth.provider_unavailable"
    assert body["title"] == "Identity provider unavailable"
