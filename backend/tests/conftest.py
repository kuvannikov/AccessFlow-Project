import secrets
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import HttpUrl, SecretStr
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.event import listen, remove
from sqlalchemy.orm import Session
from testcontainers.community.postgres import PostgresContainer

from accessflow.app import create_app
from accessflow.core.config import Settings
from accessflow.core.db import create_database_engine, get_session
from tests.database import SelectCounter
from tests.identity import ISSUER, JwksServer, SigningKey

BACKEND_DIR = Path(__file__).resolve().parents[1]
INIT_SCRIPTS_DIR = BACKEND_DIR.parent / "infra" / "postgres" / "init"


def make_settings(
    *,
    host: str,
    port: int,
    password: SecretStr,
    database: str = "accessflow",
    user: str = "accessflow_app",
) -> Settings:
    # The ".invalid" domain never resolves, so no test reaches a real identity provider.
    return Settings(
        environment="test",
        database_host=host,
        database_port=port,
        database_name=database,
        database_user=user,
        database_password=password,
        auth_issuer=ISSUER,
        auth_jwks_url=HttpUrl(f"{ISSUER}/protocol/openid-connect/certs"),
    )


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
    return make_settings(host="127.0.0.1", port=closed_port, password=SecretStr("unused"))


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def signing_key() -> SigningKey:
    return SigningKey()


@pytest.fixture
def jwks_server(signing_key: SigningKey) -> Iterator[JwksServer]:
    with JwksServer() as server:
        server.keys = [signing_key.jwk]
        yield server


@pytest.fixture(scope="session")
def postgres() -> Iterator[PostgresContainer]:
    """Disposable PostgreSQL initialized by the same scripts as the dev stack."""
    container = (
        PostgresContainer("postgres:18", password=secrets.token_hex(16), driver="psycopg")
        .with_env("ACCESSFLOW_OWNER_PASSWORD", secrets.token_hex(16))
        .with_env("ACCESSFLOW_APP_PASSWORD", secrets.token_hex(16))
        .with_env("KEYCLOAK_DB_PASSWORD", secrets.token_hex(16))
        .with_volume_mapping(INIT_SCRIPTS_DIR, "/docker-entrypoint-initdb.d", "ro")
    )
    with container:
        yield container


def database_settings(
    postgres: PostgresContainer, role: str, database: str = "accessflow"
) -> Settings:
    password_variable = f"{role.upper()}_PASSWORD"
    return make_settings(
        host=postgres.get_container_host_ip(),
        port=postgres.get_exposed_port(5432),
        password=SecretStr(postgres.env[password_variable]),
        database=database,
        user=role,
    )


def alembic_settings() -> Config:
    return Config(toml_file=BACKEND_DIR / "pyproject.toml")


@pytest.fixture(scope="session")
def database_engine(postgres: PostgresContainer) -> Iterator[Engine]:
    """Engine of the API role on a database migrated by the schema owner."""
    owner_engine = create_database_engine(database_settings(postgres, "accessflow_owner"))
    config = alembic_settings()
    config.attributes["connection"] = owner_engine
    command.upgrade(config, "head")
    owner_engine.dispose()

    engine = create_database_engine(database_settings(postgres, "accessflow_app"))
    yield engine
    engine.dispose()


@pytest.fixture
def db_connection(database_engine: Engine) -> Iterator[Connection]:
    with database_engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


@pytest.fixture
def db_session(db_connection: Connection) -> Iterator[Session]:
    """Session whose commits become savepoints; everything is rolled back after the test."""
    with Session(bind=db_connection, join_transaction_mode="create_savepoint") as session:
        yield session


@pytest.fixture
def db_client(settings: Settings, db_session: Session) -> Iterator[TestClient]:
    app = create_app(settings)
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def select_counter(db_connection: Connection) -> Iterator[SelectCounter]:
    counter = SelectCounter()
    listen(db_connection, "before_cursor_execute", counter)
    yield counter
    remove(db_connection, "before_cursor_execute", counter)


@pytest.fixture(scope="session")
def postgres_admin(postgres: PostgresContainer) -> Iterator[Engine]:
    engine = create_engine(postgres.get_connection_url(), isolation_level="AUTOCOMMIT")
    yield engine
    engine.dispose()


@pytest.fixture
def alembic_config() -> Config:
    return alembic_settings()


@pytest.fixture
def alembic_engine(postgres: PostgresContainer, postgres_admin: Engine) -> Iterator[Engine]:
    """Owner engine on an empty database of its own: migration tests go down to base."""
    database = f"migrations_{secrets.token_hex(4)}"
    with postgres_admin.connect() as connection:
        connection.execute(text(f"CREATE DATABASE {database} OWNER accessflow_owner"))
    engine = create_database_engine(database_settings(postgres, "accessflow_owner", database))
    yield engine
    engine.dispose()
    with postgres_admin.connect() as connection:
        connection.execute(text(f"DROP DATABASE {database} WITH (FORCE)"))
