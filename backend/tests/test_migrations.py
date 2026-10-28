from pytest_alembic import MigrationContext


def test_history_does_not_branch(alembic_runner: MigrationContext) -> None:
    # The built-in single-head test also demands that a revision exists.
    assert len(alembic_runner.heads) <= 1
