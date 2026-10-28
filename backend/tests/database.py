from sqlalchemy import Connection
from sqlalchemy.engine.interfaces import DBAPICursor, ExecutionContext


class SelectCounter:
    """Counts SELECT statements sent through one connection."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(
        self,
        connection: Connection,
        cursor: DBAPICursor,
        statement: str,
        parameters: object,
        context: ExecutionContext | None,
        executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            self.count += 1
