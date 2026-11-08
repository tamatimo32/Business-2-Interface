"""Configuration defaults, validation, overrides, and documentation coverage."""

import re
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import REPOSITORY_DIR, Settings


def test_defaults_are_local_and_offline_first(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path)
    assert settings.product_name == "Local AI"
    assert settings.database_url == f"sqlite+aiosqlite:///{(tmp_path / 'app.db').as_posix()}"
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.web_search_enabled is False
    assert settings.is_development is False
    assert settings.ollama_connect_timeout_seconds == 5
    assert settings.ollama_read_timeout_seconds == 120


def test_environment_overrides_and_relative_data_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRODUCT_NAME", "  Kantoor AI  ")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATA_DIR", "data/custom")
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:5173"]')
    settings = Settings(_env_file=None)
    assert settings.product_name == "Kantoor AI"
    assert settings.is_development is True
    assert settings.data_dir == REPOSITORY_DIR / "data/custom"
    assert settings.cors_origins == ["http://localhost:5173"]


@pytest.mark.parametrize(
    "values",
    [
        {"database_url": "postgresql+asyncpg://localhost/app"},
        {"database_url": "sqlite+aiosqlite:///:memory:", "app_env": "production"},
        {"cors_origins": ["*"]},
        {"cors_origins": ["http://localhost:5173/path"]},
        {"app_origin": "https://user:password@example.com"},
        {"app_origin": "https://example.com/path"},
        {"ollama_base_url": "file:///tmp/ollama"},
        {"max_output_tokens": 9000, "default_context_tokens": 8192},
        {"max_queued_per_user": 40, "max_queued_generations": 32},
        {"product_name": "bad\nname"},
        {"tz": "Not/AZone"},
    ],
)
def test_invalid_configuration_is_rejected(values: dict) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_secret_is_hidden_in_representation() -> None:
    settings = Settings(_env_file=None, secret_key=SecretStr("never-print-this-value"))
    assert "never-print-this-value" not in repr(settings)


def test_every_setting_is_documented_in_env_example() -> None:
    text = (REPOSITORY_DIR / ".env.example").read_text()
    documented = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", text, re.MULTILINE))
    assert {name.upper() for name in Settings.model_fields} <= documented
