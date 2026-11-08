"""Request correlation and content-free access logging without buffering streams."""

from time import perf_counter
from uuid import UUID, uuid4

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = structlog.get_logger(__name__)


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        supplied_id = (
            dict(scope.get("headers", []))
            .get(b"x-request-id", b"")
            .decode("ascii", errors="replace")
        )
        try:
            request_id = str(UUID(supplied_id))
        except ValueError:
            request_id = str(uuid4())
        tokens = structlog.contextvars.bind_contextvars(request_id=request_id)
        status_code = 500
        started = perf_counter()

        async def send_with_context(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["Cache-Control"] = "no-store"
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        except Exception as exc:
            # Exception text/tracebacks can contain prompts, SQL parameters, or secrets.
            logger.error("request.failed", error_type=type(exc).__name__, status_code=500)
            raise
        else:
            route = scope.get("route")
            route_path = getattr(route, "path", "unmatched")
            log = logger.debug if route_path.startswith("/api/health") else logger.info
            log(
                "request.completed",
                method=scope["method"],
                route=route_path,
                status_code=status_code,
                duration_ms=round((perf_counter() - started) * 1000, 2),
            )
        finally:
            structlog.contextvars.reset_contextvars(**tokens)
