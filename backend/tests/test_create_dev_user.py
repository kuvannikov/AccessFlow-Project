import secrets

import pytest

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
