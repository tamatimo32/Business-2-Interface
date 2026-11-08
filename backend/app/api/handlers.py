"""Convert framework, database, and service failures into one safe JSON shape."""

from http import HTTPStatus

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError, ErrorResponse

logger = structlog.get_logger(__name__)


def error_response(
    status_code: int, code: str, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    payload = ErrorResponse(error={"code": code, "message": message})
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
        headers=headers,
        media_type="application/json",
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "application.error",
            code=exc.code,
            status_code=exc.status_code,
            operation=exc.operation,
            upstream_status=exc.upstream_status,
        )
        return error_response(exc.status_code, exc.code, exc.public_message)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        try:
            message = HTTPStatus(exc.status_code).phrase
        except ValueError:
            message = "Request failed"
        return error_response(exc.status_code, code, message, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Pydantic's errors include input values, which may be private message content.
        logger.warning("request.validation_failed", error_count=len(exc.errors()))
        return error_response(422, "validation_error", "Request validation failed.")

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("database.operation_failed", error_type=type(exc).__name__)
        return error_response(503, "database_error", "Database operation failed.")

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # RequestContextMiddleware logs the exception class once, without its text.
        return error_response(500, "internal_error", "An internal error occurred.")
