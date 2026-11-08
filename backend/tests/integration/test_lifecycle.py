"""Startup migration ownership and request-scoped database dependencies."""

import sqlite3
from pathlib import Path

import httpx
from asgi_lifespan import LifespanManager

from app.api.dependencies import SessionDependency
from app.core.config import Settings
from app.core.errors import DatabaseUnavailable
from app.db.types import UTCDateTime
from app.main import create_app
from tests.conftest import default_ollama_handler


async def test_auto_migrate_uses_injected_settings_and_closes_resources(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'startup.db').as_posix()}",
        auto_migrate=True,
    )
    app = create_app(settings, ollama_transport=httpx.MockTransport(default_ollama_handler))

    @app.get("/api/test-session")
    async def session_route(session: SessionDependency) -> dict:
        from sqlalchemy import text

        return {"value": (await session.execute(text("SELECT 1"))).scalar_one()}

    async with LifespanManager(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            assert (await client.get("/api/health")).status_code == 200
            assert (await client.get("/api/test-session")).json() == {"value": 1}
        assert app.state.ollama.closed is False
    assert app.state.ollama.closed is True
    with sqlite3.connect(tmp_path / "startup.db") as connection:
        assert (
            connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "0001_initial_schema"
        )


async def test_startup_rejects_unmigrated_or_mismatched_schema(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'empty.db').as_posix()}",
        auto_migrate=False,
    )
    app = create_app(settings, ollama_transport=httpx.MockTransport(default_ollama_handler))
    try:
        async with LifespanManager(app):
            raise AssertionError("startup should have rejected an empty database")
    except* DatabaseUnavailable:
        pass


def test_utc_datetime_normalizes_aware_values() -> None:
    from datetime import UTC, datetime

    value = UTCDateTime().process_result_value(datetime(2026, 1, 1, 12), None)
    assert value.tzinfo == UTC
    assert value.hour == 12
