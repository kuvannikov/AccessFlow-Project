import secrets
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import httpx2
import pytest

from scripts import create_dev_user
from scripts.create_dev_user import ADMIN_PASSWORD_VARIABLE
from tests.dev_users import run_script

USER_ARGS = (
    "--username", "o.kuznetsova",
    "--email", "o.kuznetsova@example.test",
    "--first-name", "Ольга",
    "--last-name", "Кузнецова",
)  # fmt: skip


@pytest.fixture
def keycloak_url(closed_port: int) -> str:
    return f"http://127.0.0.1:{closed_port}"


def test_admin_password_is_required_before_prompting(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], keycloak_url: str
) -> None:
    monkeypatch.delenv(ADMIN_PASSWORD_VARIABLE, raising=False)

    exit_code = run_script(monkeypatch, *USER_ARGS, "--keycloak-url", keycloak_url, passwords=[])

    assert exit_code == 1
    assert capsys.readouterr() == (
        "",
        f"{ADMIN_PASSWORD_VARIABLE} is not set; run the script with uv run --env-file ../.env.\n",
    )


def test_mismatched_passwords_stop_before_any_request(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], keycloak_url: str
) -> None:
    monkeypatch.setenv(ADMIN_PASSWORD_VARIABLE, secrets.token_hex(16))
    password = secrets.token_urlsafe(16)

    exit_code = run_script(
        monkeypatch,
        *USER_ARGS,
        "--keycloak-url",
        keycloak_url,
        passwords=[password, f"{password}!"],
    )

    assert exit_code == 1
    assert capsys.readouterr() == ("", "The passwords do not match.\n")


def test_unreachable_keycloak_is_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], keycloak_url: str
) -> None:
    monkeypatch.setenv(ADMIN_PASSWORD_VARIABLE, secrets.token_hex(16))
    password = secrets.token_urlsafe(16)

    exit_code = run_script(
        monkeypatch, *USER_ARGS, "--keycloak-url", keycloak_url, passwords=[password, password]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err.startswith(f"Keycloak is not reachable at {keycloak_url}: ")
    assert password not in captured.err


USER_ID = "7d1c6a0e-4b0f-4a52-9f6e-0b7f6d0f1c11"


def serve_admin_api(
    monkeypatch: pytest.MonkeyPatch, assign_roles: Callable[[httpx2.Request], httpx2.Response]
) -> None:
    def handle(request: httpx2.Request) -> httpx2.Response:
        match request.method, request.url.path.rsplit("/", 1)[-1]:
            case "GET", "HR":
                return httpx2.Response(200, json={"id": "role-id", "name": "HR"})
            case "POST", "users":
                location = f"http://keycloak.test/admin/realms/accessflow/users/{USER_ID}"
                return httpx2.Response(201, headers={"Location": location})
            case _:
                return assign_roles(request)

    @contextmanager
    def admin_client(keycloak_url: str, admin_password: str) -> Iterator[httpx2.Client]:
        with httpx2.Client(
            base_url="http://keycloak.test/admin/realms/accessflow",
            transport=httpx2.MockTransport(handle),
        ) as client:
            yield client

    monkeypatch.setattr(create_dev_user, "admin_client", admin_client)
    monkeypatch.setenv(ADMIN_PASSWORD_VARIABLE, secrets.token_hex(16))


def refuse_role_assignment(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(503, json={"errorMessage": "Maintenance"})


def lose_connection(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectError("connection reset", request=request)


@pytest.mark.parametrize(
    ("assign_roles", "reason"),
    [
        pytest.param(
            refuse_role_assignment,
            "Keycloak refused POST /admin/realms/accessflow/users/"
            f"{USER_ID}/role-mappings/realm: 503 Maintenance",
            id="refused",
        ),
        pytest.param(lose_connection, "Keycloak is not reachable: connection reset", id="lost"),
    ],
)
def test_failed_role_assignment_names_the_created_user(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    assign_roles: Callable[[httpx2.Request], httpx2.Response],
    reason: str,
) -> None:
    serve_admin_api(monkeypatch, assign_roles)
    password = secrets.token_urlsafe(16)

    exit_code = run_script(
        monkeypatch,
        *USER_ARGS,
        "--hr",
        passwords=[password, password],
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == (
        f"User o.kuznetsova (id {USER_ID}) was created without the requested roles: {reason}. "
        "Assign the roles in the admin console or delete the user and run the script again.\n"
    )
    assert password not in captured.err
