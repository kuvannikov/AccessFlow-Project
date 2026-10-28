"""Migration environment. Run it with the schema owner's credentials.

Tables created by the owner receive the data-only grants for the API role
through the default privileges set up in infra/postgres/init.
"""

import logging

from alembic import context

from accessflow.core.config import Settings
from accessflow.core.db import Base, create_database_engine

if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported")

logging.basicConfig(format="%(levelname)s [%(name)s] %(message)s")
logging.getLogger("alembic").setLevel(logging.INFO)

engine = create_database_engine(Settings())
try:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
