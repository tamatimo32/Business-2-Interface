"""Application-owned resources: one database engine and one Ollama HTTP client."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import structlog
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from sqlalchemy import inspect, text

from app.core.config import BACKEND_DIR, Settings
from app.core.errors import DatabaseUnavailable
from app.core.logging import configure_logging
from app.db.session import Database
from app.services.ollama import OllamaClient

logger = structlog.get_logger(__name__)


def _alembic_config(settings: Settings | None = None) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    if settings is not None:
        config.attributes["settings"] = settings
    return config


async def _verify_schema(database: Database) -> None:
    head = ScriptDirectory.from_config(_alembic_config()).get_current_head()
    try:
        async with database.engine.connect() as connection:
            has_version_table = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).has_table("alembic_version")
            )
            if not has_version_table:
                raise DatabaseUnavailable
            revisions = set(
                (
                    await connection.execute(text("SELECT version_num FROM alembic_version"))
                ).scalars()
            )
            if revisions != {head}:
                raise DatabaseUnavailable
    except DatabaseUnavailable:
        logger.error("database.schema_not_ready", expected_revision=head)
        raise


@asynccontextmanager
async def lifespan(
    app: FastAPI,
    *,
    settings: Settings,
    ollama_transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    settings.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    database = Database(settings)
    app.state.settings = settings
    app.state.database = database
    try:
        await database.verify_connection()
        if settings.auto_migrate:
            await asyncio.to_thread(command.upgrade, _alembic_config(settings), "head")
        await _verify_schema(database)
        app.state.ollama = OllamaClient(settings, transport=ollama_transport)
        logger.info(
            "application.started",
            version=settings.app_version,
            environment=settings.app_env,
            cors_enabled=settings.is_development,
        )
        try:
            yield
        finally:
            await app.state.ollama.aclose()
            logger.info("application.stopped")
    finally:
        await database.close()
