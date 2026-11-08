"""Alembic online/offline migrations using the application's async SQLite engine."""

import asyncio

from alembic import context
from sqlalchemy import JSON
from sqlalchemy.engine import Connection

import app.models  # noqa: F401 -- register all tables before Alembic inspects metadata
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import Database
from app.db.types import UTCDateTime

config = context.config
settings = config.attributes.get("settings") or get_settings()
configure_logging(settings.log_level)
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
target_metadata = Base.metadata


def render_item(type_: str, obj: object, autogen_context: object) -> str | bool:
    """Keep generated migrations independent of evolving application type decorators."""
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    if type_ == "type" and isinstance(obj, JSON):
        autogen_context.imports.add("from sqlalchemy.dialects import postgresql")
        return 'sa.JSON().with_variant(postgresql.JSONB(), "postgresql")'
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,
        transactional_ddl=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    settings.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    database = Database(settings)
    try:
        async with database.engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
            await connection.commit()
    finally:
        await database.close()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
