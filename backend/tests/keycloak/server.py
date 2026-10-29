"""Disposable Keycloak that imports the project realm, and its admin operations for tests."""

import secrets
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx2
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import HttpWaitStrategy

IMAGE = "quay.io/keycloak/keycloak:26.8.0"
REALM = "accessflow"
REALM_FILE = Path(__file__).resolve().parents[3] / "infra" / "keycloak" / "realm-accessflow.json"
WEB_CLIENT = "accessflow-web"
# Has no audience mapper, so its tokens are not issued for the API.
FOREIGN_CLIENT = "accessflow-tests"
HTTP_PORT = 8080
MANAGEMENT_PORT = 9000
ADMIN_USERNAME = "admin"
STARTUP_TIMEOUT_SECONDS = 120
REQUEST_TIMEOUT_SECONDS = 10


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
        self.issuer = f"{url}/realms/{REALM}"
        self.jwks_url = f"{self.issuer}/protocol/openid-connect/certs"
        self._url = url
        self._admin_password = admin_password

    @contextmanager
    def _admin(self) -> Iterator[httpx2.Client]:
        # A fresh admin token for every operation: tokens of the master realm live 60 seconds.
        with httpx2.Client(
            base_url=f"{self._url}/admin/realms/{REALM}", timeout=REQUEST_TIMEOUT_SECONDS
        ) as client:
            response = client.post(
                f"{self._url}/realms/master/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": "admin-cli",
                    "username": ADMIN_USERNAME,
                    "password": self._admin_password,
                },
            ).raise_for_status()
            client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
            yield client

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
        password = secrets.token_urlsafe(24)
        with self._admin() as admin:
            # Keycloak refuses to sign in a user whose required profile fields are empty.
            response = admin.post(
                "/users",
                json={
                    "username": username,
                    "email": f"{username}@example.test",
                    "emailVerified": True,
                    "firstName": first_name,
                    "lastName": last_name,
                    "enabled": True,
                    "credentials": [{"type": "password", "value": password, "temporary": False}],
                },
            ).raise_for_status()
            user_id = response.headers["Location"].rsplit("/", 1)[-1]
            if roles:
                representations = [
                    admin.get(f"/roles/{role}").raise_for_status().json() for role in roles
                ]
                admin.post(
                    f"/users/{user_id}/role-mappings/realm", json=representations
                ).raise_for_status()
        return RealmUser(id=user_id, username=username, password=password)

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
