"""Database engine, ORM metadata and request-scoped sessions."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import URL, Engine, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from accessflow.core.config import DatabaseSettings

CONNECT_TIMEOUT_SECONDS = 5
POOL_TIMEOUT_SECONDS = 5
STATEMENT_TIMEOUT_SECONDS = 10
LOCK_TIMEOUT_SECONDS = 5
IDLE_IN_TRANSACTION_TIMEOUT_SECONDS = 30
KEEPALIVE_IDLE_SECONDS = 30
KEEPALIVE_INTERVAL_SECONDS = 10
KEEPALIVE_PROBES = 3
TCP_USER_TIMEOUT_MILLISECONDS = 30_000

# Deterministic constraint names: migrations can drop them by name, and a
# unique violation maps to an API error through the constraint name alone.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def create_database_engine(settings: DatabaseSettings, *, limit_statements: bool = True) -> Engine:
    """Engine with bounded waits on connect, on a pool slot and on a silent peer.

    The server also cancels statements and lock waits that run too long, unless
    `limit_statements` is off, which a migration needs for a slow schema change.
    """
    url = URL.create(
        "postgresql+psycopg",
        username=settings.database_user,
        password=settings.database_password.get_secret_value(),
        host=settings.database_host,
        port=settings.database_port,
        database=settings.database_name,
    )
    connect_args: dict[str, str | int] = {
        "connect_timeout": CONNECT_TIMEOUT_SECONDS,
        "keepalives": 1,
        "keepalives_idle": KEEPALIVE_IDLE_SECONDS,
        "keepalives_interval": KEEPALIVE_INTERVAL_SECONDS,
        "keepalives_count": KEEPALIVE_PROBES,
        "tcp_user_timeout": TCP_USER_TIMEOUT_MILLISECONDS,
    }
    if limit_statements:
        connect_args["options"] = (
            f"-c statement_timeout={STATEMENT_TIMEOUT_SECONDS * 1000} "
            f"-c lock_timeout={LOCK_TIMEOUT_SECONDS * 1000} "
            f"-c idle_in_transaction_session_timeout={IDLE_IN_TRANSACTION_TIMEOUT_SECONDS * 1000}"
        )
    return create_engine(
        url, pool_pre_ping=True, pool_timeout=POOL_TIMEOUT_SECONDS, connect_args=connect_args
    )


def get_session(request: Request) -> Iterator[Session]:
    """Open one session per request; services set transaction boundaries themselves."""
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
