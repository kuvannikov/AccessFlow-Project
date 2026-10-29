import secrets
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import HttpUrl

from accessflow.core.config import Settings
from tests.authorization import protected_client
from tests.keycloak.server import (
    FOREIGN_CLIENT,
    HTTP_PORT,
    WEB_CLIENT,
    KeycloakServer,
    RealmUser,
    keycloak_container,
)


@pytest.fixture(scope="session")
def keycloak() -> Iterator[KeycloakServer]:
    """Keycloak with the realm file as is, plus password sign-in that only tests use."""
    admin_password = secrets.token_hex(16)
    with keycloak_container(admin_password) as container:
        url = f"http://{container.get_container_host_ip()}:{container.get_exposed_port(HTTP_PORT)}"
        server = KeycloakServer(url, admin_password)
        server.allow_password_grant(WEB_CLIENT)
        server.create_password_client(FOREIGN_CLIENT)
        yield server


@pytest.fixture(scope="session")
def hr_user(keycloak: KeycloakServer) -> RealmUser:
    return keycloak.create_user("a.smirnova", "Анна", "Смирнова", roles=["HR"])


@pytest.fixture(scope="session")
def user_without_roles(keycloak: KeycloakServer) -> RealmUser:
    return keycloak.create_user("i.petrov", "Иван", "Петров")


@pytest.fixture
def keycloak_settings(settings: Settings, keycloak: KeycloakServer) -> Settings:
    return settings.model_copy(
        update={"auth_issuer": keycloak.issuer, "auth_jwks_url": HttpUrl(keycloak.jwks_url)}
    )


@pytest.fixture
def client(keycloak_settings: Settings) -> Iterator[TestClient]:
    with protected_client(keycloak_settings) as test_client:
        yield test_client
