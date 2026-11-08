"""Liveness and backend-mediated Ollama diagnostics; no model names are exposed."""

import asyncio

from fastapi import APIRouter

from app.api.dependencies import OllamaDependency, SettingsDependency
from app.core.errors import OllamaUnreachable
from app.schemas.health import HealthResponse, OllamaHealthResponse

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health(settings: SettingsDependency) -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version)


@router.get("/ollama", response_model=OllamaHealthResponse)
async def ollama_health(client: OllamaDependency) -> OllamaHealthResponse:
    version, models = await asyncio.gather(
        client.version(), client.list_models(), return_exceptions=True
    )
    for result in (version, models):
        if isinstance(result, OllamaUnreachable):
            return OllamaHealthResponse(reachable=False, version=None, model_count=None)
    for result in (version, models):
        if isinstance(result, BaseException):
            raise result
    return OllamaHealthResponse(reachable=True, version=version, model_count=len(models))
