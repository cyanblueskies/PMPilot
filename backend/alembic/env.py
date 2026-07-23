from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings

# Importing app.models registers every table on Base.metadata. Autogenerate only
# sees what is registered, so a model missing from app/models/__init__.py comes
# out silently absent from the migration.
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Wired to the real ORM metadata. While this was None, --autogenerate emitted
# empty migrations with no error.
target_metadata = Base.metadata

# The URL comes from .env, not from alembic.ini, so there is exactly one place
# the connection string is defined. Percent signs are escaped because
# ConfigParser interpolates them.
config.set_main_option(
    "sqlalchemy.url", get_settings().database_url.replace("%", "%%")
)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Without this, autogenerate ignores column type changes and a
            # migration can silently drift from the models.
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
