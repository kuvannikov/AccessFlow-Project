import pytest
from pydantic import ValidationError

from accessflow.app import create_app


def test_create_app_fails_without_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ACCESSFLOW_ENVIRONMENT", raising=False)

    with pytest.raises(ValidationError):
        create_app()
