"""Isolated settings, migrated temporary databases, and mocked ASGI/Ollama clients."""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from asgi_lifespan import LifespanManager

from app.core.config import BACKEND_DIR, Settings
from app.db.session import Database
from app.main import create_app
from app.services.ollama import OllamaClient


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
        auto_migrate=False,
        secret_key=None,
        log_level="INFO",
    )


def alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


@pytest.fixture
async def database(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Database]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATA_DIR", str(settings.data_dir))
    monkeypatch.setenv("DATABASE_URL", settings.database_url)
    await asyncio.to_thread(command.upgrade, alembic_config(), "head")
    runtime_database = Database(settings)
    try:
        yield runtime_database
    finally:
        await runtime_database.close()


def default_ollama_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/version":
        return httpx.Response(200, json={"version": "0.12.0"})
    if request.url.path == "/api/tags":
        return httpx.Response(
            200,
            json={"models": [{"name": "chat:latest"}, {"name": "embed:latest"}]},
        )
    return httpx.Response(404, json={"error": "upstream route not found"})


@pytest.fixture
def client_factory(settings: Settings, database: Database):
    @asynccontextmanager
    async def make(
        handler: Callable[[httpx.Request], httpx.Response] | None = None,
        *,
        updates: dict | None = None,
        configure: Callable | None = None,
    ) -> AsyncIterator[httpx.AsyncClient]:
        runtime_settings = settings.model_copy(update=updates or {})
        application = create_app(
            runtime_settings,
            ollama_transport=httpx.MockTransport(handler or default_ollama_handler),
        )
        if configure is not None:
            configure(application)
        async with LifespanManager(application):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application, raise_app_exceptions=False),
                base_url="http://testserver",
            ) as client:
                yield client

    return make


@pytest.fixture
async def client(client_factory) -> AsyncIterator[httpx.AsyncClient]:
    async with client_factory() as test_client:
        yield test_client


@pytest.fixture
def ollama_factory(settings: Settings):
    @asynccontextmanager
    async def make(
        handler: Callable[[httpx.Request], httpx.Response], *, updates: dict | None = None
    ) -> AsyncIterator[OllamaClient]:
        runtime_settings = settings.model_copy(update=updates or {})
        client = OllamaClient(runtime_settings, transport=httpx.MockTransport(handler))
        try:
            yield client
        finally:
            await client.aclose()

    return make
