"""Async, backend-only Ollama client with one shared connection pool.

Chat and pull expose Ollama's parsed NDJSON records, not browser SSE. The chat
phase will translate those records into the public streaming contract. Pull is
an explicit operator operation and is never called automatically by the app.
"""

import json
import math
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any

import httpx
import structlog
from pydantic import TypeAdapter, ValidationError

from app.core.config import Settings
from app.core.errors import ModelNotFound, OllamaError, OllamaInvalidResponse, OllamaUnreachable
from app.schemas.ollama import OllamaModel

logger = structlog.get_logger(__name__)
_MODEL_LIST = TypeAdapter(list[OllamaModel])


def _model_name(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 256 or any(ord(character) < 32 for character in value):
        raise ValueError("invalid Ollama model name")
    return value


def _translate_transport_error(exc: Exception, operation: str) -> OllamaError:
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return OllamaUnreachable(operation=operation)
    if isinstance(exc, httpx.DecodingError):
        return OllamaInvalidResponse(operation=operation)
    return OllamaError(operation=operation)


class OllamaClient:
    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._settings = settings
        self._timeout = httpx.Timeout(
            connect=settings.ollama_connect_timeout_seconds,
            read=settings.ollama_read_timeout_seconds,
            write=settings.ollama_write_timeout_seconds,
            pool=settings.ollama_pool_timeout_seconds,
        )
        self._client = httpx.AsyncClient(
            base_url=settings.ollama_base_url.rstrip("/") + "/",
            timeout=self._timeout,
            limits=httpx.Limits(
                max_connections=settings.ollama_max_connections,
                max_keepalive_connections=max(1, settings.ollama_max_connections // 2),
                keepalive_expiry=30.0,
            ),
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            headers={"Accept": "application/json", "User-Agent": "Local-AI-Appliance/0.1"},
        )

    @property
    def closed(self) -> bool:
        return self._client.is_closed

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _check_status(
        self, response: httpx.Response, operation: str, model_operation: bool
    ) -> None:
        if response.status_code < 300:
            return
        if not response.is_stream_consumed:
            await response.aread()
        upstream_error = ""
        try:
            payload = response.json()
            if isinstance(payload, dict) and isinstance(payload.get("error"), str):
                upstream_error = payload["error"].lower()
        except (ValueError, UnicodeDecodeError):
            pass
        logger.warning(
            "ollama.http_error",
            operation=operation,
            upstream_status=response.status_code,
        )
        if model_operation and (
            response.status_code == 404
            or ("model" in upstream_error and "not found" in upstream_error)
        ):
            raise ModelNotFound(operation=operation, upstream_status=response.status_code)
        raise OllamaError(operation=operation, upstream_status=response.status_code)

    async def _send(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        model_operation: bool = False,
    ) -> httpx.Response:
        try:
            response = await self._client.request(method, path, json=payload)
        except httpx.TransportError as exc:
            raise _translate_transport_error(exc, path) from exc
        await self._check_status(response, path, model_operation)
        return response

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        model_operation: bool = False,
    ) -> Any:
        response = await self._send(method, path, payload=payload, model_operation=model_operation)
        try:
            return response.json()
        except (ValueError, UnicodeDecodeError) as exc:
            raise OllamaInvalidResponse(operation=path) from exc

    @asynccontextmanager
    async def _stream(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        model_operation: bool = True,
        request_timeout: httpx.Timeout | None = None,
    ) -> AsyncIterator[httpx.Response]:
        try:
            async with self._client.stream(
                "POST", path, json=dict(payload), timeout=request_timeout or self._timeout
            ) as response:
                await self._check_status(response, path, model_operation)
                yield response
        except httpx.TransportError as exc:
            raise _translate_transport_error(exc, path) from exc

    async def _ndjson(
        self, response: httpx.Response, operation: str, *, model_operation: bool = True
    ) -> AsyncIterator[dict[str, Any]]:
        buffer = bytearray()
        limit = self._settings.ollama_max_stream_line_bytes

        def parse(line: bytes) -> dict[str, Any]:
            try:
                value = json.loads(line)
            except (ValueError, UnicodeDecodeError) as exc:
                raise OllamaInvalidResponse(operation=operation) from exc
            if not isinstance(value, dict):
                raise OllamaInvalidResponse(operation=operation)
            if value.get("error"):
                message = str(value["error"]).lower()
                if model_operation and "model" in message and "not found" in message:
                    raise ModelNotFound(operation=operation)
                raise OllamaError(operation=operation)
            return value

        async for block in response.aiter_bytes():
            buffer.extend(block)
            while True:
                newline = buffer.find(b"\n")
                if newline < 0:
                    if len(buffer) > limit:
                        raise OllamaInvalidResponse(operation=operation)
                    break
                line = bytes(buffer[:newline]).rstrip(b"\r")
                del buffer[: newline + 1]
                if line.strip():
                    yield parse(line)
        if len(buffer) > limit:
            raise OllamaInvalidResponse(operation=operation)
        if buffer.strip():
            yield parse(bytes(buffer))

    async def version(self) -> str:
        payload = await self._request_json("GET", "api/version")
        if not isinstance(payload, dict) or not isinstance(payload.get("version"), str):
            raise OllamaInvalidResponse(operation="api/version")
        return payload["version"]

    async def _models(self, path: str) -> list[OllamaModel]:
        payload = await self._request_json("GET", path)
        if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
            raise OllamaInvalidResponse(operation=path)
        try:
            return _MODEL_LIST.validate_python(payload["models"])
        except ValidationError as exc:
            raise OllamaInvalidResponse(operation=path) from exc

    async def list_models(self) -> list[OllamaModel]:
        return await self._models("api/tags")

    async def running_models(self) -> list[OllamaModel]:
        return await self._models("api/ps")

    async def show_model(self, model: str) -> dict[str, Any]:
        payload = await self._request_json(
            "POST", "api/show", payload={"model": _model_name(model)}, model_operation=True
        )
        if not isinstance(payload, dict):
            raise OllamaInvalidResponse(operation="api/show")
        return payload

    async def chat(
        self,
        model: str,
        messages: Sequence[Mapping[str, Any]],
        *,
        options: Mapping[str, Any] | None = None,
        keep_alive: str | int | None = None,
        response_format: str | Mapping[str, Any] | None = None,
        think: bool | str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield parsed /api/chat records, preserving content whitespace exactly."""
        if not messages:
            raise ValueError("at least one chat message is required")
        payload: dict[str, Any] = {
            "model": _model_name(model),
            "messages": list(messages),
            "stream": True,
        }
        if options is not None:
            payload["options"] = dict(options)
        payload["keep_alive"] = (
            self._settings.ollama_keep_alive if keep_alive is None else keep_alive
        )
        if response_format is not None:
            payload["format"] = response_format
        if think is not None:
            payload["think"] = think
        async with self._stream("api/chat", payload) as response:
            async for chunk in self._ndjson(response, "api/chat"):
                yield chunk

    async def embed(
        self,
        model: str,
        input: str | Sequence[str],
        *,
        truncate: bool = True,
        options: Mapping[str, Any] | None = None,
        keep_alive: str | int | None = None,
    ) -> list[list[float]]:
        if isinstance(input, str):
            if not input:
                raise ValueError("embedding input cannot be empty")
        elif not input:
            raise ValueError("at least one embedding input is required")
        payload: dict[str, Any] = {
            "model": _model_name(model),
            "input": input,
            "truncate": truncate,
            "keep_alive": self._settings.ollama_keep_alive if keep_alive is None else keep_alive,
        }
        if options is not None:
            payload["options"] = dict(options)
        result = await self._request_json(
            "POST", "api/embed", payload=payload, model_operation=True
        )
        embeddings = result.get("embeddings") if isinstance(result, dict) else None
        if not isinstance(embeddings, list) or not embeddings:
            raise OllamaInvalidResponse(operation="api/embed")
        dimensions: int | None = None
        for vector in embeddings:
            if not isinstance(vector, list) or not vector:
                raise OllamaInvalidResponse(operation="api/embed")
            if dimensions is None:
                dimensions = len(vector)
            if len(vector) != dimensions or any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                for value in vector
            ):
                raise OllamaInvalidResponse(operation="api/embed")
        return embeddings

    async def pull(self, model: str) -> AsyncIterator[dict[str, Any]]:
        """Explicitly pull a model, yielding progress records. May use the internet."""
        timeout = httpx.Timeout(
            connect=self._settings.ollama_connect_timeout_seconds,
            read=self._settings.ollama_pull_read_timeout_seconds,
            write=self._settings.ollama_write_timeout_seconds,
            pool=self._settings.ollama_pool_timeout_seconds,
        )
        async with self._stream(
            "api/pull", {"model": _model_name(model), "stream": True}, request_timeout=timeout
        ) as response:
            async for chunk in self._ndjson(response, "api/pull"):
                yield chunk

    async def delete(self, model: str) -> None:
        await self._send(
            "DELETE", "api/delete", payload={"model": _model_name(model)}, model_operation=True
        )
