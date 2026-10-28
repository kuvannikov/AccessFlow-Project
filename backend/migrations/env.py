"""Migration environment. Run it with the schema owner's credentials.

Tables created by the owner receive the data-only grants for the API role
through the default privileges set up in infra/postgres/init.
"""

import logging

from alembic import context
from sqlalchemy import Engine

from accessflow.core.config import Settings
from accessflow.core.db import Base, create_database_engine


def run_migrations(engine: Engine) -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported")

# Tests supply their own engine under the "connection" key, the name pytest-alembic
# uses; the command line connects with the settings from the environment.
supplied_engine: Engine | None = context.config.attributes.get("connection")
if supplied_engine is not None:
    run_migrations(supplied_engine)
else:
    logging.basicConfig(format="%(levelname)s [%(name)s] %(message)s")
    logging.getLogger("alembic").setLevel(logging.INFO)
    engine = create_database_engine(Settings())
    try:
        run_migrations(engine)
    finally:
        engine.dispose()
