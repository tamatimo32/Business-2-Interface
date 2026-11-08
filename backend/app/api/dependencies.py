"""Typed request dependencies shared by current and future routers."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import get_session
from app.services.ollama import OllamaClient


def get_runtime_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_ollama(request: Request) -> OllamaClient:
    return request.app.state.ollama


SessionDependency = Annotated[AsyncSession, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_runtime_settings)]
OllamaDependency = Annotated[OllamaClient, Depends(get_ollama)]
