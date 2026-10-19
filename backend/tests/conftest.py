from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from accessflow.app import create_app
from accessflow.core.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
