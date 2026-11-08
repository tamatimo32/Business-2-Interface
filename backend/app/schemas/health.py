"""Public foundation health responses."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class OllamaHealthResponse(BaseModel):
    reachable: bool
    version: str | None = None
    model_count: int | None = Field(default=None, ge=0)
