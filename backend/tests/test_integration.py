"""Run only against a separately named, disposable Compose project."""

import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
import jwt
import psycopg
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.db import Base
from app.employee_data import SlugSuggestionExhausted, find_available_slug
from app.models import Employee  # noqa: F401 - register model metadata for migration comparison

if os.getenv("ACCESSFLOW_INTEGRATION") != "1":
    pytest.skip(
        "Set ACCESSFLOW_INTEGRATION=1 for the isolated Compose stack", allow_module_level=True
    )

API = os.getenv("ACCESSFLOW_TEST_API")
KEYCLOAK = os.getenv("ACCESSFLOW_TEST_KEYCLOAK")
POSTGRES_PORT = os.getenv("ACCESSFLOW_TEST_POSTGRES_PORT")
if (API, KEYCLOAK, POSTGRES_PORT) != (
    "http://127.0.0.1:18000",
    "http://127.0.0.1:18081/auth",
    "15432",
):
    raise pytest.UsageError("Integration requires explicit isolated endpoints 18000/18081/15432")
POSTGRES_PORT = int(POSTGRES_PORT)


def postgres_connection():
    return psycopg.connect(
        host="127.0.0.1",
        port=POSTGRES_PORT,
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


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
    client_uuid = response.headers["Location"].rsplit("/", 1)[-1]
    role = httpx.get(f"{KEYCLOAK}/admin/realms/accessflow/roles/HR", headers=headers, timeout=15)
    role.raise_for_status()
    result = {}
    user_ids = []
    for kind in ("hr", "employee"):
        email = f"integration-{kind}-{unique}@example.org"
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
        user_id = created.headers["Location"].rsplit("/", 1)[-1]
        user_ids.append(user_id)
        if kind == "hr":
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
    yield AccessTokens(result)
    for user_id in user_ids:
        deleted = httpx.delete(
            f"{KEYCLOAK}/admin/realms/accessflow/users/{user_id}", headers=headers, timeout=15
        )
        assert deleted.status_code == 204
    deleted = httpx.delete(
        f"{KEYCLOAK}/admin/realms/accessflow/clients/{client_uuid}", headers=headers, timeout=15
    )
    assert deleted.status_code == 204


@pytest.fixture
def employee_ids():
    created_ids = []
    yield created_ids
    with postgres_connection() as connection:
        connection.execute("DELETE FROM employees WHERE id = ANY(%s)", (created_ids,))


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
        port=POSTGRES_PORT,
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
    engine = create_engine("postgresql+psycopg://", creator=postgres_connection)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            assert compare_metadata(context, Base.metadata) == []
    finally:
        engine.dispose()


def test_postgres_concurrent_slug_conflict(tokens, employee_ids):
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
    employee_ids.extend(
        response.json()["id"] for response in responses if response.status_code == 201
    )
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


def test_postgres_concurrent_email_conflict_and_recovery(tokens, employee_ids):
    unique = uuid4().hex[:10]
    data = {
        "first_name": "Integration",
        "last_name": "Email",
        "position": "Engineer",
        "department": "Test",
        "start_date": "2026-10-12",
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda number: post_employee(
                    tokens["hr"],
                    {
                        **data,
                        "email": f"email-{unique}@example.org"
                        if number == 1
                        else f"EMAIL-{unique}@example.org",
                        "slug": f"email-{unique}-{number}",
                    },
                ),
                (1, 2),
            )
        )
    assert sorted(response.status_code for response in responses) == [201, 409]
    employee_ids.extend(
        response.json()["id"] for response in responses if response.status_code == 201
    )
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["detail"]["code"] == "email_conflict"
    recovered = post_employee(
        tokens["hr"],
        {**data, "email": f"recovered-{unique}@example.org", "slug": f"recovered-{unique}"},
    )
    assert recovered.status_code == 201
    employee_ids.append(recovered.json()["id"])


@pytest.mark.parametrize(
    "occupied,expected_queries", [(0, 1), (99, 1), (100, 2), (999, 10), (1000, 10)]
)
def test_postgres_slug_candidate_limit_and_query_cost(tokens, occupied, expected_queries):
    first_name = f"Audit{uuid4().hex[:10]}"
    root = f"{first_name.lower()}.bound"
    headers = {"Authorization": f"Bearer {tokens['hr']}"}
    employee_ids = []
    with postgres_connection() as connection:
        for number in range(1, occupied + 1):
            slug = root if number == 1 else f"{root}-{number}"
            employee_ids.append(
                connection.execute(
                    "INSERT INTO employees (first_name, last_name, email, position, department, start_date, slug) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (
                        first_name,
                        "Bound",
                        f"{slug}@example.org",
                        "Test",
                        "Test",
                        "2026-10-12",
                        slug,
                    ),
                ).fetchone()[0]
            )
    engine = create_engine("postgresql+psycopg://", creator=postgres_connection)
    queries = []

    @event.listens_for(engine, "before_cursor_execute")
    def count_queries(_connection, _cursor, statement, parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT") and "employees" in statement:
            queries.append(len(parameters))

    try:
        with Session(engine) as session:
            if occupied == 1000:
                with pytest.raises(SlugSuggestionExhausted):
                    find_available_slug(session, root)
            else:
                expected = root if occupied == 0 else f"{root}-{occupied + 1}"
                assert find_available_slug(session, root) == expected
        assert len(queries) == expected_queries
        assert all(size == 100 for size in queries)
        response = httpx.post(
            f"{API}/api/employees/slug-suggestion",
            headers=headers,
            json={"first_name": first_name, "last_name": "Bound"},
            timeout=15,
        )
        if occupied == 1000:
            assert response.status_code == 409
            assert response.json()["detail"]["code"] == "slug_suggestion_exhausted"
        else:
            assert response.status_code == 200
            assert response.json()["slug"] == expected
    finally:
        engine.dispose()
        with postgres_connection() as connection:
            connection.execute("DELETE FROM employees WHERE id = ANY(%s)", (employee_ids,))


@pytest.mark.parametrize("field", ["middle_name", "position", "department"])
def test_postgres_rejects_nul_without_poisoning_session(tokens, field, employee_ids):
    unique = uuid4().hex[:10]
    data = {
        "first_name": "Integration",
        "last_name": "Validation",
        "email": f"nul-{unique}@example.org",
        "position": "Engineer",
        "department": "Test",
        "start_date": "2026-10-12",
        "slug": f"nul-{unique}",
    }
    rejected = post_employee(tokens["hr"], {**data, field: "invalid\x00text"})
    assert rejected.status_code == 422
    assert "input" not in rejected.json()["detail"][0]
    accepted = post_employee(tokens["hr"], data)
    assert accepted.status_code == 201
    employee_ids.append(accepted.json()["id"])


def test_employee_deletion_keeps_matching_keycloak_account(tokens, employee_ids):
    # Claims from the real test token identify the already provisioned account;
    # the API still validates the signed token on every request.
    identity = jwt.decode(tokens["hr"], options={"verify_signature": False})
    created = post_employee(
        tokens["hr"],
        {
            "first_name": "Integration",
            "last_name": "Account",
            "email": identity["email"],
            "position": "Engineer",
            "department": "Test",
            "start_date": "2026-10-12",
            "slug": f"account-{uuid4().hex[:10]}",
        },
    )
    assert created.status_code == 201
    employee_id = created.json()["id"]
    employee_ids.append(employee_id)
    headers = {"Authorization": f"Bearer {tokens['hr']}"}
    removed = httpx.delete(f"{API}/api/employees/{employee_id}", headers=headers, timeout=15)
    assert removed.status_code == 204
    assert not removed.content
    assert (
        httpx.delete(f"{API}/api/employees/{employee_id}", headers=headers, timeout=15).status_code
        == 404
    )
    admin = httpx.post(
        f"{KEYCLOAK}/realms/master/protocol/openid-connect/token",
        data={
            "client_id": "admin-cli",
            "grant_type": "password",
            "username": os.environ["KEYCLOAK_ADMIN"],
            "password": os.environ["KEYCLOAK_ADMIN_PASSWORD"],
        },
        timeout=15,
    )
    admin.raise_for_status()
    account = httpx.get(
        f"{KEYCLOAK}/admin/realms/accessflow/users/{identity['sub']}",
        headers={"Authorization": f"Bearer {admin.json()['access_token']}"},
        timeout=15,
    )
    assert account.status_code == 200
    assert account.json()["enabled"] is True


def test_keycloak_bounds_anonymous_login_event_usernames():
    """The ordinary browser flow must reject overlong usernames before event logging."""
    import base64
    import hashlib
    import subprocess
    from datetime import UTC, datetime
    from html.parser import HTMLParser
    from pathlib import Path
    from urllib.parse import urlsplit

    class LoginForm(HTMLParser):
        action = None

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == "form" and values.get("id") == "kc-form-login":
                self.action = values.get("action")

    started = datetime.now(UTC).isoformat()
    marker = "integration-login-limit-" + uuid4().hex
    usernames = {size: marker + "x" * (size - len(marker)) for size in (128, 256, 4096)}
    for username in usernames.values():
        verifier = uuid4().hex + uuid4().hex
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        with httpx.Client(timeout=15, follow_redirects=True) as browser:
            login = browser.get(
                f"{KEYCLOAK.replace('127.0.0.1', 'localhost')}/realms/accessflow/protocol/openid-connect/auth",
                params={
                    "client_id": "accessflow-web",
                    "redirect_uri": "http://localhost:5173/hr",
                    "response_type": "code",
                    "scope": "openid",
                    "state": uuid4().hex,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                },
            )
            assert login.status_code == 200
            form = LoginForm()
            form.feed(login.text)
            assert form.action is not None, "Missing ordinary browser login form"
            action = urlsplit(form.action)
            assert action.hostname in {"localhost", "127.0.0.1"}
            assert action.port == 18081
            assert action.path.startswith("/auth/realms/accessflow/login-actions/")
            # Browser flow uses the documented canonical loopback hostname.
            browser_endpoint = KEYCLOAK.replace("127.0.0.1", "localhost")
            action_url = browser_endpoint.removesuffix("/auth") + action.path
            if action.query:
                action_url += "?" + action.query
            rejected = browser.post(
                action_url,
                # Browsers accept Secure cookies on localhost HTTP; httpx does not.
                # Only this synthetic session is forwarded to the validated local action.
                headers={
                    "Origin": browser_endpoint.removesuffix("/auth"),
                    "Referer": str(login.url),
                    "Cookie": "; ".join(
                        f"{cookie.name}={cookie.value}" for cookie in browser.cookies.jar
                    ),
                },
                data={
                    "username": username,
                    "password": "synthetic-not-a-secret",
                    "credentialId": "",
                },
            )
            assert rejected.status_code == 200
    output = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "compose.yaml",
            "-f",
            "compose.integration.yaml",
            "-p",
            "accessflow_integration",
            "logs",
            "--no-color",
            "--since",
            started,
            "keycloak",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    occurrences = {size: output.count(username) for size, username in usernames.items()}
    assert occurrences[128] >= 1, "Missing normal-length event-log positive control"
    assert occurrences[256] == 0, "256-character username reached event logging"
    assert occurrences[4096] == 0, "4096-character username reached event logging"
