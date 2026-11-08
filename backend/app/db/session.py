"""One async engine per application process, with PRAGMAs on every connection."""

from collections.abc import AsyncIterator
from pathlib import Path

import structlog
from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.core.config import Settings
from app.core.errors import DatabaseUnavailable

logger = structlog.get_logger(__name__)


class Database:
    def __init__(self, settings: Settings) -> None:
        url = make_url(settings.database_url)
        if url.drivername != "sqlite+aiosqlite":
            raise ValueError("only asynchronous SQLite is supported in this release")
        self.database_path: Path | None = (
            Path(url.database).resolve()
            if url.database and url.database not in {":memory:", ""}
            else None
        )
        kwargs: dict = {
            "pool_pre_ping": True,
            "connect_args": {"timeout": settings.sqlite_busy_timeout_ms / 1000},
        }
        if self.database_path is None:
            kwargs["poolclass"] = StaticPool
        self.engine: AsyncEngine = create_async_engine(settings.database_url, **kwargs)
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
        )
        synchronous = {"NORMAL": 1, "FULL": 2}[settings.sqlite_synchronous]

        @event.listens_for(self.engine.sync_engine, "connect")
        def configure_sqlite(dbapi_connection: object, connection_record: object) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                mode = cursor.fetchone()[0]
                cursor.execute(f"PRAGMA synchronous={synchronous}")
                cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout_ms}")
                if str(mode).lower() not in {"wal", "memory"}:
                    raise RuntimeError("SQLite WAL mode could not be enabled")
                cursor.execute("PRAGMA foreign_keys")
                if cursor.fetchone()[0] != 1:
                    raise RuntimeError("SQLite foreign keys could not be enabled")
            finally:
                cursor.close()

    async def verify_connection(self) -> None:
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception as exc:
            logger.error("database.connection_failed", error_type=type(exc).__name__)
            raise DatabaseUnavailable from exc

    async def close(self) -> None:
        await self.engine.dispose()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Request-scoped unit of work. Services commit explicitly; reads do not write."""
    database: Database = request.app.state.database
    async with database.session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
