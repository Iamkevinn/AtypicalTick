import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Permite "import config" / "import db" etc. cuando alembic corre
# desde la raiz del proyecto (mismo path que main.py usa).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATABASE_URL, SQLITE_DB_PATH

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# NOTA (Fase 2 - migración Supabase/Render):
# En vez de depender de "sqlalchemy.url" fijo en alembic.ini, construimos
# la URL de conexión con la MISMA lógica que repositories/db_repository.py:
# si DATABASE_URL está configurada (Postgres/Supabase), se usa esa. Si no,
# se usa el archivo SQLite local (SQLITE_DB_PATH), igual que en desarrollo.
# psycopg (driver v3) se declara explícitamente con "postgresql+psycopg://"
# para que SQLAlchemy no intente usar psycopg2 (que no está instalado).
if DATABASE_URL:
    _url = DATABASE_URL
    if _url.startswith("postgresql://") and "+psycopg" not in _url:
        _url = _url.replace("postgresql://", "postgresql+psycopg://", 1)
    config.set_main_option("sqlalchemy.url", _url)
else:
    config.set_main_option("sqlalchemy.url", f"sqlite:///{SQLITE_DB_PATH}")

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No usamos modelos de SQLAlchemy ORM (el proyecto usa SQL crudo via
# repositories/db_repository.py), asi que no hay target_metadata para
# autogenerate. Las migraciones de este proyecto se escriben a mano.
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
