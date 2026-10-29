"""Disposable Keycloak that imports the project realm, and its admin operations for tests."""

import secrets
from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path

import httpx2
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import HttpWaitStrategy

from scripts import create_dev_user
from scripts.create_dev_user import ADMIN_USERNAME, REALM, REQUEST_TIMEOUT_SECONDS, NewUser

IMAGE = "quay.io/keycloak/keycloak:26.8.0"
REALM_FILE = Path(__file__).resolve().parents[3] / "infra" / "keycloak" / "realm-accessflow.json"
WEB_CLIENT = "accessflow-web"
# Has no audience mapper, so its tokens are not issued for the API.
FOREIGN_CLIENT = "accessflow-tests"
HTTP_PORT = 8080
MANAGEMENT_PORT = 9000
STARTUP_TIMEOUT_SECONDS = 120


def keycloak_container(admin_password: str) -> DockerContainer:
    return (
        DockerContainer(IMAGE)
        .with_command(["start-dev", "--import-realm"])
        .with_envs(
            KC_BOOTSTRAP_ADMIN_USERNAME=ADMIN_USERNAME,
            KC_BOOTSTRAP_ADMIN_PASSWORD=admin_password,
            KC_HEALTH_ENABLED="true",
        )
        .with_exposed_ports(HTTP_PORT, MANAGEMENT_PORT)
        .with_volume_mapping(REALM_FILE, f"/opt/keycloak/data/import/{REALM_FILE.name}", "ro")
        .waiting_for(
            HttpWaitStrategy(MANAGEMENT_PORT, "/health/ready").with_startup_timeout(
                STARTUP_TIMEOUT_SECONDS
            )
        )
    )


@dataclass(frozen=True)
class RealmUser:
    id: str
    username: str
    password: str


class KeycloakServer:
    def __init__(self, url: str, admin_password: str) -> None:
        self.url = url
        self.admin_password = admin_password
        self.issuer = f"{url}/realms/{REALM}"
        self.jwks_url = f"{self.issuer}/protocol/openid-connect/certs"

    def _admin(self) -> AbstractContextManager[httpx2.Client]:
        # A fresh admin token for every operation: tokens of the master realm live 60 seconds.
        return create_dev_user.admin_client(self.url, self.admin_password)

    def allow_password_grant(self, client_id: str) -> None:
        """Let the client issue tokens for a username and password, so tests need no browser."""
        with self._admin() as admin:
            response = admin.get("/clients", params={"clientId": client_id}).raise_for_status()
            (client,) = response.json()
            client["directAccessGrantsEnabled"] = True
            admin.put(f"/clients/{client['id']}", json=client).raise_for_status()

    def create_password_client(self, client_id: str) -> None:
        """Add a public client that only issues tokens for a username and password."""
        with self._admin() as admin:
            admin.post(
                "/clients",
                json={
                    "clientId": client_id,
                    "publicClient": True,
                    "standardFlowEnabled": False,
                    "directAccessGrantsEnabled": True,
                },
            ).raise_for_status()

    def create_user(
        self, username: str, first_name: str, last_name: str, *, roles: Sequence[str] = ()
    ) -> RealmUser:
        user = NewUser(
            username=username,
            email=f"{username}@example.test",
            first_name=first_name,
            last_name=last_name,
            password=secrets.token_urlsafe(24),
            roles=tuple(roles),
        )
        with self._admin() as admin:
            user_id = create_dev_user.create_user(admin, user)
        return RealmUser(id=user_id, username=user.username, password=user.password)

    def find_user(self, username: str) -> str | None:
        """ID of the user with exactly this username, if there is one."""
        with self._admin() as admin:
            response = admin.get("/users", params={"username": username, "exact": "true"})
            users = response.raise_for_status().json()
        return users[0]["id"] if users else None

    def access_token(self, user: RealmUser, client_id: str = WEB_CLIENT) -> str:
        response = httpx2.post(
            f"{self.issuer}/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": client_id,
                "username": user.username,
                "password": user.password,
                "scope": "openid",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        ).raise_for_status()
        token: str = response.json()["access_token"]
        return token
