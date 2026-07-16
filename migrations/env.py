"""
Alembic migration environment.

Reads the database URL from application settings (never duplicated in
`alembic.ini`) and supports the project's async engine by running the
migration script inside `connection.run_sync(...)`.

The target is Supabase PostgreSQL, so the engine here is built with the
same `connect_args` (mandatory TLS, optional PgBouncer compatibility) as
the app's own engine in `app/database/session.py` — otherwise `alembic
upgrade head` would fail to negotiate TLS with Supabase.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from app.config.settings import get_settings
from app.database.base import Base
from app.database.session import build_connect_args

# Import model modules here so Alembic's autogenerate can see them.
from app.models import otp_challenge  # noqa: F401
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
config.set_main_option("sqlalchemy.url", str(settings.DATABASE_URL))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable: AsyncEngine = create_async_engine(
        str(settings.DATABASE_URL), connect_args=build_connect_args(settings)
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
