import httpx2
import pytest
from fastapi.testclient import TestClient

from accessflow.core.config import Settings
from tests.identity import bearer
from tests.keycloak.server import FOREIGN_CLIENT, KeycloakServer, RealmUser

pytestmark = pytest.mark.keycloak


def test_discovery_matches_configured_endpoints(
    keycloak: KeycloakServer, keycloak_settings: Settings
) -> None:
    response = httpx2.get(f"{keycloak.issuer}/.well-known/openid-configuration")

    assert response.status_code == 200
    document = response.json()
    assert document["issuer"] == keycloak_settings.auth_issuer
    assert document["jwks_uri"] == str(keycloak_settings.auth_jwks_url)


def test_hr_user_is_identified(
    client: TestClient, keycloak: KeycloakServer, hr_user: RealmUser
) -> None:
    response = client.get("/api/me", headers=bearer(keycloak.access_token(hr_user)))

    assert response.status_code == 200
    assert response.json() == {
        "displayName": "Анна Смирнова",
        "roles": ["HR", "default-roles-accessflow", "offline_access", "uma_authorization"],
    }


def test_hr_user_is_admitted(
    client: TestClient, keycloak: KeycloakServer, hr_user: RealmUser
) -> None:
    response = client.get("/test/hr", headers=bearer(keycloak.access_token(hr_user)))

    assert response.status_code == 200
    assert response.json() == {"subject": hr_user.id}


def test_user_without_role_is_forbidden(
    client: TestClient, keycloak: KeycloakServer, user_without_roles: RealmUser
) -> None:
    response = client.get("/test/hr", headers=bearer(keycloak.access_token(user_without_roles)))

    assert response.status_code == 403
    assert response.json()["code"] == "auth.forbidden"


def test_token_for_another_client_is_unauthorized(
    client: TestClient, keycloak: KeycloakServer, hr_user: RealmUser
) -> None:
    token = keycloak.access_token(hr_user, client_id=FOREIGN_CLIENT)

    response = client.get("/api/me", headers=bearer(token))

    assert response.status_code == 401
    assert response.json()["code"] == "auth.invalid_token"
