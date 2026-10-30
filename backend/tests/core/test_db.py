import pytest
from sqlalchemy import (
    CheckConstraint,
    Column,
    Connection,
    Engine,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    text,
)
from sqlalchemy.exc import ProgrammingError
from testcontainers.community.postgres import PostgresContainer

from accessflow.core.db import NAMING_CONVENTION, Base, create_database_engine
from tests.conftest import database_settings


def test_api_role_cannot_change_schema(db_connection: Connection) -> None:
    with pytest.raises(ProgrammingError, match="permission denied for schema public"):
        db_connection.execute(text("CREATE TABLE probes (id integer)"))


@pytest.mark.parametrize(
    "statement",
    [
        "SELECT version_num FROM alembic_version",
        "INSERT INTO alembic_version (version_num) VALUES ('forged')",
        "UPDATE alembic_version SET version_num = 'forged'",
        "DELETE FROM alembic_version",
    ],
)
def test_api_role_cannot_touch_migration_state(db_connection: Connection, statement: str) -> None:
    with pytest.raises(ProgrammingError, match="permission denied for table alembic_version"):
        db_connection.execute(text(statement))


def test_models_use_the_naming_convention() -> None:
    assert Base.metadata.naming_convention == NAMING_CONVENTION


def test_constraint_names_follow_convention() -> None:
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    Table("teams", metadata, Column("id", Integer, primary_key=True))
    members = Table(
        "members",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("email", Text, unique=True),
        Column("team_id", ForeignKey("teams.id"), index=True),
        CheckConstraint("id > 0", name="id_positive"),
    )

    names = {constraint.name for constraint in members.constraints}
    names |= {index.name for index in members.indexes}

    assert names == {
        "pk_members",
        "uq_members_email",
        "fk_members_team_id_teams",
        "ck_members_id_positive",
        "ix_members_team_id",
    }


def show(connection: Connection, setting: str) -> str:
    return str(connection.execute(text(f"SHOW {setting}")).scalar_one())


def test_server_limits_statements_locks_and_idle_transactions(db_connection: Connection) -> None:
    assert show(db_connection, "statement_timeout") == "10s"
    assert show(db_connection, "lock_timeout") == "5s"
    assert show(db_connection, "idle_in_transaction_session_timeout") == "30s"


def test_connection_detects_a_silent_peer(db_connection: Connection) -> None:
    driver_connection = db_connection.connection.driver_connection
    assert driver_connection is not None

    parameters = driver_connection.info.get_parameters()

    assert parameters["connect_timeout"] == "5"
    assert parameters["keepalives"] == "1"
    assert parameters["keepalives_idle"] == "30"
    assert parameters["keepalives_interval"] == "10"
    assert parameters["keepalives_count"] == "3"
    assert parameters["tcp_user_timeout"] == "30000"


def test_migration_engine_does_not_limit_statements(postgres: PostgresContainer) -> None:
    engine: Engine = create_database_engine(
        database_settings(postgres, "accessflow_owner"), limit_statements=False
    )
    try:
        with engine.connect() as connection:
            assert show(connection, "statement_timeout") == "0"
            assert show(connection, "lock_timeout") == "0"
    finally:
        engine.dispose()


def test_tables_of_the_owner_are_open_to_the_api_role_for_data_only(
    postgres: PostgresContainer,
) -> None:
    engine = create_database_engine(
        database_settings(postgres, "accessflow_owner"), limit_statements=False
    )
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text("CREATE TABLE privilege_probe (id integer)"))
            granted = {
                privilege: connection.execute(
                    text("SELECT has_table_privilege('accessflow_app', 'privilege_probe', :p)"),
                    {"p": privilege},
                ).scalar_one()
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES")
            }
            transaction.rollback()
    finally:
        engine.dispose()

    assert granted == {
        "SELECT": True,
        "INSERT": True,
        "UPDATE": True,
        "DELETE": True,
        "TRUNCATE": False,
        "REFERENCES": False,
    }
