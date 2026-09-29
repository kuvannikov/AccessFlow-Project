"""Run only against a separately named, disposable Compose project."""

import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
import psycopg
import pytest

if os.getenv("ACCESSFLOW_INTEGRATION") != "1":
    pytest.skip(
        "Set ACCESSFLOW_INTEGRATION=1 for the isolated Compose stack", allow_module_level=True
    )

API = "http://127.0.0.1:8080"
KEYCLOAK = "http://127.0.0.1:8081/auth"


class AccessTokens(dict):
    def __repr__(self) -> str:
        return "<access tokens redacted>"


def post_employee(token: str, data: dict) -> httpx.Response:
    return httpx.post(
        f"{API}/api/employees",
        json=data,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )


@pytest.fixture(scope="module")
def tokens():
    required = (
        "KEYCLOAK_ADMIN",
        "KEYCLOAK_ADMIN_PASSWORD",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    )
    assert all(os.getenv(name) for name in required), "Missing isolated test environment settings"
    admin_token = httpx.post(
        f"{KEYCLOAK}/realms/master/protocol/openid-connect/token",
        data={
            "client_id": "admin-cli",
            "grant_type": "password",
            "username": os.environ["KEYCLOAK_ADMIN"],
            "password": os.environ["KEYCLOAK_ADMIN_PASSWORD"],
        },
        timeout=15,
    )
    admin_token.raise_for_status()
    headers = {"Authorization": f"Bearer {admin_token.json()['access_token']}"}
    unique = uuid4().hex[:12]
    client_id = f"accessflow-integration-{unique}"
    test_client = {
        "clientId": client_id,
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": True,
        "standardFlowEnabled": False,
        "directAccessGrantsEnabled": True,
        "protocolMappers": [
            {
                "name": "api-audience",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-audience-mapper",
                "config": {
                    "included.custom.audience": "accessflow-api",
                    "access.token.claim": "true",
                },
            }
        ],
    }
    response = httpx.post(
        f"{KEYCLOAK}/admin/realms/accessflow/clients", headers=headers, json=test_client, timeout=15
    )
    assert response.status_code == 201
    role = httpx.get(f"{KEYCLOAK}/admin/realms/accessflow/roles/HR", headers=headers, timeout=15)
    role.raise_for_status()
    result = {}
    for kind in ("hr", "employee"):
        email = f"integration-{kind}-{unique}@example.test"
        password = secrets.token_urlsafe(24)
        user = {
            "username": email,
            "email": email,
            "firstName": "Integration",
            "lastName": kind,
            "emailVerified": True,
            "enabled": True,
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        }
        created = httpx.post(
            f"{KEYCLOAK}/admin/realms/accessflow/users", headers=headers, json=user, timeout=15
        )
        assert created.status_code == 201
        if kind == "hr":
            user_id = created.headers["Location"].rsplit("/", 1)[-1]
            assigned = httpx.post(
                f"{KEYCLOAK}/admin/realms/accessflow/users/{user_id}/role-mappings/realm",
                headers=headers,
                json=[role.json()],
                timeout=15,
            )
            assert assigned.status_code == 204
        granted = httpx.post(
            f"{KEYCLOAK}/realms/accessflow/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": client_id,
                "username": email,
                "password": password,
            },
            timeout=15,
        )
        granted.raise_for_status()
        result[kind] = granted.json()["access_token"]
    return AccessTokens(result)


def test_real_keycloak_roles_and_migration(tokens):
    assert httpx.get(f"{API}/api/employees", timeout=15).status_code == 401
    assert (
        httpx.get(
            f"{API}/api/employees",
            headers={"Authorization": f"Bearer {tokens['employee']}"},
            timeout=15,
        ).status_code
        == 403
    )
    assert (
        httpx.get(
            f"{API}/api/employees", headers={"Authorization": f"Bearer {tokens['hr']}"}, timeout=15
        ).status_code
        == 200
    )
    with psycopg.connect(
        host="127.0.0.1",
        port=5432,
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    ) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0001",)
        constraints = {
            row[0]
            for row in connection.execute(
                "SELECT conname FROM pg_constraint WHERE conrelid = 'employees'::regclass AND contype = 'u'"
            )
        }
        assert {"uq_employees_email", "uq_employees_slug"} <= constraints


def test_postgres_concurrent_slug_conflict(tokens):
    unique = uuid4().hex[:10]
    first_name = f"Audit{unique}"
    last_name = "Ivanov"
    suggestion = httpx.post(
        f"{API}/api/employees/slug-suggestion",
        headers={"Authorization": f"Bearer {tokens['hr']}"},
        json={"first_name": first_name, "last_name": last_name},
        timeout=15,
    )
    assert suggestion.status_code == 200
    slug = suggestion.json()["slug"]
    data = {
        "first_name": first_name,
        "last_name": last_name,
        "middle_name": None,
        "position": "Engineer",
        "department": "Test",
        "start_date": "2026-10-12",
        "slug": slug,
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda number: post_employee(
                    tokens["hr"], {**data, "email": f"integration-{unique}-{number}@example.org"}
                ),
                (1, 2),
            )
        )
    assert sorted(response.status_code for response in responses) == [201, 409], [
        (response.status_code, [item["loc"] for item in response.json().get("detail", [])])
        for response in responses
    ]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["detail"]["code"] == "slug_conflict"
    next_suggestion = httpx.post(
        f"{API}/api/employees/slug-suggestion",
        headers={"Authorization": f"Bearer {tokens['hr']}"},
        json={"first_name": first_name, "last_name": last_name},
        timeout=15,
    )
    assert next_suggestion.json()["slug"] == f"{slug}-2"
    created = next(response for response in responses if response.status_code == 201)
    assert created.json()["slug"] == slug
