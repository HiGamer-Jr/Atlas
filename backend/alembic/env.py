from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app.core.config import MigrationSettings
from app.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def configure_and_run(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    supplied = config.attributes.get("connection")
    if supplied is not None:
        configure_and_run(supplied)
        return
    settings = MigrationSettings()
    config.attributes["runtime_role"] = settings.database_runtime_role
    engine = create_engine(
        settings.migration_database_url, poolclass=pool.NullPool, hide_parameters=True
    )
    try:
        with engine.connect() as connection:
            configure_and_run(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    raise RuntimeError(
        "Offline migrations are disabled: role and privilege checks require PostgreSQL."
    )
else:
    run_migrations_online()
