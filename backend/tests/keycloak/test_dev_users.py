import secrets

import pytest
from fastapi.testclient import TestClient

from scripts.create_dev_user import ADMIN_PASSWORD_VARIABLE
from tests.dev_users import run_script
from tests.identity import bearer
from tests.keycloak.server import KeycloakServer, RealmUser

pytestmark = pytest.mark.keycloak


@pytest.fixture(autouse=True)
def admin_password(monkeypatch: pytest.MonkeyPatch, keycloak: KeycloakServer) -> None:
    monkeypatch.setenv(ADMIN_PASSWORD_VARIABLE, keycloak.admin_password)


def user_args(
    keycloak: KeycloakServer, username: str, first_name: str, last_name: str
) -> list[str]:
    return [
        "--username", username,
        "--email", f"{username}@example.test",
        "--first-name", first_name,
        "--last-name", last_name,
        "--keycloak-url", keycloak.url,
    ]  # fmt: skip


def test_hr_user_signs_in_with_the_typed_password(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    keycloak: KeycloakServer,
    client: TestClient,
) -> None:
    password = secrets.token_urlsafe(16)

    exit_code = run_script(
        monkeypatch,
        *user_args(keycloak, "o.kuznetsova", "Ольга", "Кузнецова"),
        "--hr",
        passwords=[password, password],
    )

    user_id = keycloak.find_user("o.kuznetsova")
    assert exit_code == 0
    assert user_id is not None
    assert capsys.readouterr() == (
        f"Created user o.kuznetsova (id {user_id}), assigned roles: HR.\n",
        "",
    )
    token = keycloak.access_token(RealmUser(id=user_id, username="o.kuznetsova", password=password))
    me = client.get("/api/me", headers=bearer(token))
    assert me.status_code == 200
    assert me.json()["displayName"] == "Ольга Кузнецова"
    assert client.get("/test/hr", headers=bearer(token)).status_code == 200


def test_user_without_hr_is_signed_in_but_forbidden(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    keycloak: KeycloakServer,
    client: TestClient,
) -> None:
    password = secrets.token_urlsafe(16)

    exit_code = run_script(
        monkeypatch,
        *user_args(keycloak, "d.sokolov", "Дмитрий", "Соколов"),
        passwords=[password, password],
    )

    user_id = keycloak.find_user("d.sokolov")
    assert exit_code == 0
    assert user_id is not None
    assert capsys.readouterr() == (
        f"Created user d.sokolov (id {user_id}), assigned roles: none.\n",
        "",
    )
    token = keycloak.access_token(RealmUser(id=user_id, username="d.sokolov", password=password))
    assert client.get("/api/me", headers=bearer(token)).status_code == 200
    assert client.get("/test/hr", headers=bearer(token)).status_code == 403


def test_password_below_realm_policy_creates_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], keycloak: KeycloakServer
) -> None:
    password = secrets.token_urlsafe(16)[:11]

    exit_code = run_script(
        monkeypatch,
        *user_args(keycloak, "e.volkova", "Елена", "Волкова"),
        "--hr",
        passwords=[password, password],
    )

    assert exit_code == 1
    assert capsys.readouterr() == (
        "",
        "Keycloak refused POST /admin/realms/accessflow/users: "
        "400 Invalid password: minimum length 12.\n",
    )
    assert keycloak.find_user("e.volkova") is None


def test_existing_username_is_rejected(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], keycloak: KeycloakServer
) -> None:
    password = secrets.token_urlsafe(16)
    first = user_args(keycloak, "m.orlov", "Михаил", "Орлов")
    assert run_script(monkeypatch, *first, passwords=[password, password]) == 0
    capsys.readouterr()
    second = [*first, "--email", "m.orlov.second@example.test"]

    exit_code = run_script(monkeypatch, *second, passwords=[password, password])

    assert exit_code == 1
    assert capsys.readouterr() == (
        "",
        "Keycloak refused POST /admin/realms/accessflow/users: "
        "409 User exists with same username\n",
    )


def test_wrong_admin_password_is_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], keycloak: KeycloakServer
) -> None:
    monkeypatch.setenv(ADMIN_PASSWORD_VARIABLE, secrets.token_hex(16))
    password = secrets.token_urlsafe(16)

    exit_code = run_script(
        monkeypatch,
        *user_args(keycloak, "n.lebedeva", "Наталья", "Лебедева"),
        passwords=[password, password],
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err.startswith(
        "Keycloak refused POST /realms/master/protocol/openid-connect/token: "
    )
    assert captured.err.endswith(" Invalid user credentials\n")
    assert keycloak.find_user("n.lebedeva") is None
