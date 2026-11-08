"""Small, tolerant schemas for Ollama model catalog responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OllamaModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    model: str | None = None
    modified_at: datetime | None = None
    size: int | None = Field(default=None, ge=0)
    digest: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime | None = None
    size_vram: int | None = Field(default=None, ge=0)
