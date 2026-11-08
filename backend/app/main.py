"""FastAPI application factory for the backend foundation."""

from functools import partial

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.handlers import register_exception_handlers
from app.api.routes.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.lifecycle import lifespan
from app.core.middleware import RequestContextMiddleware


def create_app(
    settings: Settings | None = None,
    *,
    ollama_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    application = FastAPI(
        title=settings.product_name,
        version=settings.app_version,
        lifespan=partial(lifespan, settings=settings, ollama_transport=ollama_transport),
        # Interactive docs need locally bundled assets; never use FastAPI's CDN defaults.
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.is_development else None,
        telemetry={
            "tracing": False,
            "metrics": False,
            "logs": False,
            "operation_spans": False,
            "auto_configure": False,
        },
    )
    application.add_middleware(RequestContextMiddleware)
    if settings.is_development:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID", "Idempotency-Key"],
            expose_headers=["X-Request-ID"],
            max_age=600,
        )
    register_exception_handlers(application)
    application.include_router(health_router)
    return application


app = create_app()
