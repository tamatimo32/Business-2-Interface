"""Health, error-envelope, CORS, and privacy tests without external services."""

import json
from uuid import UUID

import httpx
import pytest

from app._version import __version__


async def test_fastapi_native_telemetry_is_explicitly_disabled(client_factory) -> None:
    def configure(app) -> None:
        for key in ("tracing", "metrics", "logs", "operation_spans", "auto_configure"):
            assert app._telemetry[key] is False

    async with client_factory(configure=configure) as client:
        assert (await client.get("/api/health")).status_code == 200


async def test_application_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    UUID(response.headers["x-request-id"])


async def test_ollama_health_is_backend_mediated(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/health/ollama")
    assert response.status_code == 200
    assert response.json() == {"reachable": True, "version": "0.12.0", "model_count": 2}
    assert "chat:latest" not in response.text


async def test_ollama_unreachable_is_a_degraded_diagnostic(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private-upstream-detail", request=request)

    async with client_factory(handler) as client:
        response = await client.get("/api/health/ollama")
    assert response.status_code == 200
    assert response.json() == {"reachable": False, "version": None, "model_count": None}
    assert "private-upstream-detail" not in response.text


async def test_invalid_upstream_payload_uses_common_error(client_factory) -> None:
    async with client_factory(lambda request: httpx.Response(200, text="not json")) as client:
        response = await client.get("/api/health/ollama")
    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "ollama_invalid_response",
            "message": "Ollama returned an invalid response.",
        }
    }


async def test_unknown_route_and_method_use_common_error(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Not Found"}}
    response = await client.post("/api/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
    assert "GET" in response.headers["allow"]


async def test_validation_and_unexpected_errors_never_echo_input(client_factory, capfd) -> None:
    def configure(app) -> None:
        @app.get("/api/test-validation")
        async def validation_route(number: int) -> dict:
            return {"number": number}

        @app.get("/api/test-failure")
        async def failure_route() -> None:
            raise RuntimeError("private-prompt-must-not-leak")

    async with client_factory(configure=configure) as client:
        validation = await client.get("/api/test-validation?number=private-prompt-must-not-leak")
        failure = await client.get("/api/test-failure")
    assert validation.status_code == 422
    assert validation.json() == {
        "error": {"code": "validation_error", "message": "Request validation failed."}
    }
    assert failure.status_code == 500
    assert failure.json() == {
        "error": {"code": "internal_error", "message": "An internal error occurred."}
    }
    captured = capfd.readouterr()
    assert (
        "private-prompt-must-not-leak"
        not in captured.out + captured.err + validation.text + failure.text
    )
    events = [json.loads(line) for line in captured.out.splitlines() if line.startswith("{")]
    assert any(event.get("event") == "request.failed" for event in events)


@pytest.mark.parametrize("environment", ["production", "test"])
async def test_cors_absent_outside_development(client_factory, environment: str) -> None:
    async with client_factory(updates={"app_env": environment}) as client:
        response = await client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        preflight = await client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        docs = await client.get("/docs")
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-origin" not in preflight.headers
    assert preflight.status_code == 405
    assert docs.status_code == 404


async def test_development_cors_is_exact_origin_only(client_factory) -> None:
    async with client_factory(updates={"app_env": "development"}) as client:
        allowed = await client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        rejected = await client.get("/api/health", headers={"Origin": "https://untrusted.example"})
        docs = await client.get("/docs")
        openapi = await client.get("/openapi.json")
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert "access-control-allow-origin" not in rejected.headers
    assert docs.status_code == 404
    assert openapi.status_code == 200
    assert "cdn.jsdelivr.net" not in openapi.text
