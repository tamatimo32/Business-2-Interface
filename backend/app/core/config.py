"""Validated environment configuration.

Infrastructure values are read from the process environment and the repository's
.env file. Environment variables take precedence. Settings marked as reserved
are validated now but are not activated until their corresponding phase.
"""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from app._version import __version__

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_DIR = BACKEND_DIR.parent


def _validate_http_origin(value: str, *, origin_only: bool = False) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or (origin_only and parsed.path not in {"", "/"})
    ):
        raise ValueError("must be an HTTP(S) origin without credentials, query, or fragment")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid port") from exc
    if port == 0:
        raise ValueError("port must be positive")
    return value.rstrip("/")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "test", "production"] = Field(
        default="production", description="Runtime mode; only development enables CORS."
    )
    app_origin: str = Field(
        default="https://ai.internal.example.com",
        description="Canonical browser origin, reserved for Origin checks in the auth phase.",
    )
    product_name: str = Field(
        default="Local AI", min_length=1, max_length=80, description="Runtime product branding."
    )
    brand_logo_path: Path | None = Field(
        default=None, description="Trusted local logo override; branding endpoints arrive later."
    )
    default_locale: Literal["nl", "fr", "de", "en"] = Field(
        default="en", description="Fallback UI locale."
    )
    host: str = Field(default="127.0.0.1", description="Local bind address; Docker uses 0.0.0.0.")
    port: int = Field(default=8000, ge=1, le=65535, description="Backend HTTP port.")
    data_dir: Path = Field(
        default=REPOSITORY_DIR / "data",
        description="Persistent local data directory; relative paths use the repository root.",
    )
    database_url: str | None = Field(
        default=None,
        repr=False,
        description="SQLite async URL; defaults to DATA_DIR/app.db. Other engines are not enabled.",
    )
    secret_key: SecretStr | None = Field(
        default=None,
        repr=False,
        description="Reserved for Phase 3 CSRF signing; authentication will require a strong key.",
    )
    sqlite_busy_timeout_ms: int = Field(
        default=5000, ge=0, le=60000, description="SQLite writer-contention timeout."
    )
    sqlite_synchronous: Literal["NORMAL", "FULL"] = Field(
        default="NORMAL", description="WAL durability/performance trade-off."
    )
    auto_migrate: bool = Field(
        default=False, description="Apply Alembic migrations at startup; enabled in the container."
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"],
        description="Exact Vite origins, honored only in development. JSON array in .env.",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Structured log level; request bodies are never logged."
    )
    tz: str = Field(
        default="Europe/Brussels", description="Operational timezone; stored timestamps remain UTC."
    )

    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434", description="Backend-only Ollama endpoint."
    )
    default_model: str = Field(
        default="qwen2.5:7b",
        description="Proposed local chat model; never downloaded automatically.",
    )
    embedding_model: str = Field(
        default="bge-m3", description="Local multilingual embedding model for Phase 7."
    )
    ollama_connect_timeout_seconds: float = Field(
        default=5.0, gt=0, le=60, description="Ollama TCP connection timeout."
    )
    ollama_read_timeout_seconds: float = Field(
        default=120.0, gt=0, le=1800, description="Inactivity timeout between generation reads."
    )
    ollama_write_timeout_seconds: float = Field(
        default=30.0, gt=0, le=300, description="Timeout for sending an Ollama request."
    )
    ollama_pool_timeout_seconds: float = Field(
        default=5.0, gt=0, le=60, description="Timeout waiting for a shared connection-pool slot."
    )
    ollama_pull_read_timeout_seconds: float = Field(
        default=600.0, gt=0, le=7200, description="Inactivity timeout for explicit operator pulls."
    )
    ollama_max_connections: int = Field(
        default=20, ge=1, le=100, description="Shared HTTP connection-pool ceiling."
    )
    ollama_max_stream_line_bytes: int = Field(
        default=1048576, ge=1024, le=16777216, description="Bound a single NDJSON record."
    )
    ollama_keep_alive: str = Field(
        default="5m", min_length=1, max_length=32, description="Ollama model residency duration."
    )
    max_concurrent_generations: int = Field(
        default=1, ge=1, le=16, description="Reserved for the Phase 4 generation scheduler."
    )
    max_queued_generations: int = Field(
        default=32, ge=1, le=512, description="Reserved global generation queue bound."
    )
    max_queued_per_user: int = Field(
        default=2, ge=1, le=32, description="Reserved per-user generation queue bound."
    )
    generation_timeout_seconds: int = Field(
        default=300, ge=1, le=7200, description="Reserved maximum generation lifetime."
    )
    default_context_tokens: int = Field(
        default=8192, ge=512, le=131072, description="Server-controlled context budget."
    )
    max_output_tokens: int = Field(
        default=2048, ge=1, le=32768, description="Server-controlled output budget."
    )
    session_idle_minutes: int = Field(
        default=60, ge=1, le=1440, description="Reserved session idle expiry."
    )
    session_absolute_hours: int = Field(
        default=12, ge=1, le=168, description="Reserved absolute session expiry."
    )
    cookie_secure: bool = Field(
        default=True, description="Reserved cookie policy; false only for local HTTP development."
    )
    documents_enabled: bool = Field(
        default=True, description="Document feature default; document routes arrive in Phase 7."
    )
    web_search_enabled: bool = Field(
        default=False, description="Optional outbound search; requires licensing approval."
    )
    searxng_base_url: str = Field(
        default="http://searxng:8080", description="Reserved backend-only SearXNG endpoint."
    )
    max_upload_bytes: int = Field(
        default=26214400, ge=1024, le=1073741824, description="Reserved per-document upload limit."
    )
    default_user_storage_bytes: int = Field(
        default=1073741824, ge=1024, description="Reserved default per-user storage quota."
    )
    max_documents_per_conversation: int = Field(
        default=10, ge=1, le=100, description="Reserved conversation attachment limit."
    )
    max_document_pages: int = Field(
        default=500, ge=1, le=10000, description="Reserved extraction page limit."
    )
    max_document_chunks: int = Field(
        default=2000, ge=1, le=100000, description="Reserved per-document chunk limit."
    )
    embed_batch_size: int = Field(
        default=16, ge=1, le=256, description="Reserved Ollama embedding batch size."
    )
    ingestion_workers: int = Field(
        default=1, ge=1, le=4, description="Reserved bounded ingestion worker count."
    )
    rag_top_k: int = Field(default=6, ge=1, le=20, description="Reserved retrieval budget.")
    audit_retention_days: int = Field(
        default=365, ge=1, le=3650, description="Reserved audit retention policy."
    )
    backup_retention_count: int = Field(
        default=7, ge=1, le=100, description="Reserved local backup retention policy."
    )

    @field_validator("product_name")
    @classmethod
    def validate_product_name(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(character) < 32 for character in value):
            raise ValueError("product name must be nonempty and contain no control characters")
        return value

    @field_validator("app_origin")
    @classmethod
    def validate_app_origin(cls, value: str) -> str:
        return _validate_http_origin(value, origin_only=True)

    @field_validator("ollama_base_url", "searxng_base_url")
    @classmethod
    def validate_service_url(cls, value: str) -> str:
        return _validate_http_origin(value)

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, values: list[str]) -> list[str]:
        return [_validate_http_origin(value, origin_only=True) for value in values]

    @field_validator("default_model", "embedding_model")
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 256 or any(ord(character) < 32 for character in value):
            raise ValueError("model name must contain 1–256 characters without controls")
        return value

    @field_validator("tz")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("unknown IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def resolve_paths_and_database(self) -> "Settings":
        if not self.data_dir.is_absolute():
            self.data_dir = REPOSITORY_DIR / self.data_dir
        self.data_dir = self.data_dir.resolve()
        if self.brand_logo_path is not None and not self.brand_logo_path.is_absolute():
            self.brand_logo_path = (REPOSITORY_DIR / self.brand_logo_path).resolve()
        if self.database_url is None:
            self.database_url = f"sqlite+aiosqlite:///{(self.data_dir / 'app.db').as_posix()}"
        url = make_url(self.database_url)
        if url.drivername != "sqlite+aiosqlite":
            raise ValueError("only sqlite+aiosqlite URLs are supported in this release")
        if url.database in {None, "", ":memory:"} and self.app_env != "test":
            raise ValueError("persistent SQLite file storage is required outside tests")
        if self.max_output_tokens > self.default_context_tokens:
            raise ValueError("MAX_OUTPUT_TOKENS cannot exceed DEFAULT_CONTEXT_TOKENS")
        if self.max_queued_per_user > self.max_queued_generations:
            raise ValueError("MAX_QUEUED_PER_USER cannot exceed MAX_QUEUED_GENERATIONS")
        return self

    @property
    def app_version(self) -> str:
        return __version__

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


def get_settings() -> Settings:
    """Construct a fresh validated snapshot; application lifespan owns the runtime snapshot."""
    return Settings()
