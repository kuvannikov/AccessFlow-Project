import pytest
from pydantic import ValidationError

from accessflow.core.config import Settings


def test_reads_environment_from_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACCESSFLOW_ENVIRONMENT", "test")

    assert Settings().environment == "test"


def test_missing_environment_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ACCESSFLOW_ENVIRONMENT", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_unknown_environment_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACCESSFLOW_ENVIRONMENT", "staging")

    with pytest.raises(ValidationError):
        Settings()
