import socket
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from accessflow.app import create_app
from accessflow.core.config import Settings


@pytest.fixture
def closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port


@pytest.fixture
def settings(closed_port: int) -> Settings:
    # Nothing listens on the database port, so a test that needs a real
    # database fails fast instead of reaching the dev stack.
    return Settings(
        environment="test",
        database_host="127.0.0.1",
        database_port=closed_port,
        database_name="accessflow",
        database_user="accessflow_app",
        database_password=SecretStr("unused"),
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
