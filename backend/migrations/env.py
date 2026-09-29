"""Alembic environment: models from app.db.schema, database from Settings (tech.md §5.7)."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import Settings
from app.db.schema import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def include_name(name: str | None, type_: str, parent_names: object) -> bool:
    # procrastinate owns its tables (§5.6): its SQL creates them, autogenerate leaves them alone.
    return not (type_ == "table" and name is not None and name.startswith("procrastinate_"))


# Tests pass a throwaway database through Config.attributes.
url = config.attributes.get("database_url") or Settings().DATABASE_URL.get_secret_value()
with create_engine(url, poolclass=pool.NullPool).connect() as connection:
    context.configure(
        connection=connection, target_metadata=Base.metadata, include_name=include_name
    )
    with context.begin_transaction():
        context.run_migrations()
