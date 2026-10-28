import pytest
from pydantic import ValidationError

from accessflow.core.config import Settings

REQUIRED_VARIABLES = {
    "ACCESSFLOW_ENVIRONMENT": "test",
    "ACCESSFLOW_DATABASE_HOST": "db.example.test",
    "ACCESSFLOW_DATABASE_NAME": "accessflow",
    "ACCESSFLOW_DATABASE_USER": "accessflow_app",
    "ACCESSFLOW_DATABASE_PASSWORD": "private-password",
}


@pytest.fixture(autouse=True)
def environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in REQUIRED_VARIABLES.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("ACCESSFLOW_DATABASE_PORT", raising=False)


def test_reads_settings_from_environment() -> None:
    settings = Settings()

    assert settings.environment == "test"
    assert settings.database_host == "db.example.test"
    assert settings.database_port == 5432
    assert settings.database_password.get_secret_value() == "private-password"


@pytest.mark.parametrize("name", REQUIRED_VARIABLES)
def test_missing_variable_fails(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.delenv(name)

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    ("name", "value"),
    [("ACCESSFLOW_ENVIRONMENT", "staging"), ("ACCESSFLOW_DATABASE_PORT", "70000")],
)
def test_invalid_value_fails(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings()


def test_password_stays_out_of_errors_and_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "private-password" not in repr(Settings())

    monkeypatch.delenv("ACCESSFLOW_DATABASE_HOST")
    with pytest.raises(ValidationError) as caught:
        Settings()

    assert "private-password" not in str(caught.value)
