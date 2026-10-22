"""Migraciones manuales con DDL y revisión atómicos en SQLite."""

from logging.config import fileConfig

from alembic import context
from app.infrastructure.database import build_engine, get_db_path

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
path = config.attributes.get("db_path", get_db_path())
config.set_main_option("sqlalchemy.url", f"sqlite:///{path}")
# Sin modelo completo, None rechaza autogenerate. MetaData vacío propondría borrados.
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        transactional_ddl=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = build_engine(path)
    try:
        # El evento connect configura PRAGMA antes de la transacción.
        # begin() solo no emite BEGIN físico con sqlite3 en modo legacy.
        with engine.connect() as connection, connection.begin():
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                transactional_ddl=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
