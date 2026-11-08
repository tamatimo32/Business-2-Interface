"""Ollama protocol tests using httpx.MockTransport only."""

import json

import httpx
import pytest

from app.core.errors import ModelNotFound, OllamaError, OllamaInvalidResponse, OllamaUnreachable


class ChunkedStream(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes], size: int = 3) -> None:
        self.chunks = chunks
        self.size = size
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            for offset in range(0, len(chunk), self.size):
                yield chunk[offset : offset + self.size]

    async def aclose(self) -> None:
        self.closed = True


async def test_catalog_show_and_version(ollama_factory) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.12.0"})
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [{"name": "chat:latest", "size": 123, "details": {"family": "test"}}]
                },
            )
        if request.url.path == "/api/ps":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "chat:latest",
                            "size_vram": 100,
                            "expires_at": "2026-01-01T00:00:00Z",
                        }
                    ]
                },
            )
        if request.url.path == "/api/show":
            assert json.loads(request.content) == {"model": "chat:latest"}
            return httpx.Response(200, json={"capabilities": ["completion"], "details": {}})
        raise AssertionError("unexpected path")

    async with ollama_factory(handler) as client:
        assert await client.version() == "0.12.0"
        models = await client.list_models()
        assert models[0].name == "chat:latest"
        assert models[0].details["family"] == "test"
        running = await client.running_models()
        assert running[0].size_vram == 100
        assert (await client.show_model("chat:latest"))["capabilities"] == ["completion"]
        assert client.closed is False
    assert client.closed is True
    assert [request.url.path for request in requests] == [
        "/api/version",
        "/api/tags",
        "/api/ps",
        "/api/show",
    ]


async def test_chat_parses_split_utf8_ndjson_and_preserves_whitespace(ollama_factory) -> None:
    records = [
        {
            "model": "chat:latest",
            "message": {"role": "assistant", "content": "Bonjour"},
            "done": False,
        },
        {
            "model": "chat:latest",
            "message": {"role": "assistant", "content": " été\n"},
            "done": False,
        },
        {
            "model": "chat:latest",
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "eval_count": 4,
        },
    ]
    body = (
        "\r\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\r\n"
    ).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.method == "POST"
        assert request.url.path == "/api/chat"
        assert payload["stream"] is True
        assert payload["model"] == "chat:latest"
        assert payload["options"] == {"temperature": 0.2}
        assert payload["keep_alive"] == "5m"
        return httpx.Response(200, stream=ChunkedStream([body]))

    async with ollama_factory(handler) as client:
        chunks = [
            chunk
            async for chunk in client.chat(
                "chat:latest",
                [{"role": "user", "content": "private test prompt"}],
                options={"temperature": 0.2},
            )
        ]
    assert [chunk["message"]["content"] for chunk in chunks] == ["Bonjour", " été\n", ""]
    assert chunks[-1]["done"] is True
    assert chunks[-1]["eval_count"] == 4


async def test_chat_cancellation_closes_upstream_stream(ollama_factory) -> None:
    stream = ChunkedStream(
        [
            b'{"message":{"content":"first"},"done":false}\n',
            b'{"message":{"content":"second"},"done":true}\n',
        ],
        size=1024,
    )

    async with ollama_factory(lambda request: httpx.Response(200, stream=stream)) as client:
        generator = client.chat("chat:latest", [{"role": "user", "content": "test"}])
        assert (await anext(generator))["message"]["content"] == "first"
        await generator.aclose()
    assert stream.closed is True


@pytest.mark.parametrize(
    ("status", "payload", "expected"),
    [
        (404, {"error": "model missing"}, ModelNotFound),
        (400, {"error": "model 'missing' not found"}, ModelNotFound),
        (500, {"error": "private upstream detail"}, OllamaError),
    ],
)
async def test_upstream_http_errors_are_classified_and_sanitized(
    ollama_factory, status: int, payload: dict, expected: type[Exception]
) -> None:
    async with ollama_factory(lambda request: httpx.Response(status, json=payload)) as client:
        with pytest.raises(expected) as caught:
            await client.show_model("missing:latest")
    assert "private upstream detail" not in str(caught.value)
    assert caught.value.upstream_status == status


async def test_connection_failure_is_unreachable(ollama_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private network detail", request=request)

    async with ollama_factory(handler) as client:
        with pytest.raises(OllamaUnreachable) as caught:
            await client.list_models()
    assert "private network detail" not in str(caught.value)


@pytest.mark.parametrize(
    "body",
    [b"not-json\n", b"[]\n", b'{"message":', b'{"error":"registry denied"}\n'],
)
async def test_invalid_or_error_ndjson_is_rejected(ollama_factory, body: bytes) -> None:
    expected = OllamaError if b"registry denied" in body else OllamaInvalidResponse
    async with ollama_factory(lambda request: httpx.Response(200, content=body)) as client:
        with pytest.raises(expected):
            _ = [
                chunk async for chunk in client.chat("chat", [{"role": "user", "content": "test"}])
            ]


async def test_oversized_ndjson_record_is_bounded(ollama_factory) -> None:
    body = json.dumps({"message": {"content": "x" * 2048}}).encode()
    async with ollama_factory(
        lambda request: httpx.Response(200, content=body),
        updates={"ollama_max_stream_line_bytes": 1024},
    ) as client:
        with pytest.raises(OllamaInvalidResponse):
            _ = [
                chunk async for chunk in client.chat("chat", [{"role": "user", "content": "test"}])
            ]


async def test_embed_uses_api_embed_and_validates_vectors(ollama_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embed"
        payload = json.loads(request.content)
        assert payload["input"] == ["one", "two"]
        assert payload["truncate"] is False
        return httpx.Response(200, json={"model": "embed", "embeddings": [[0.1, 0.2], [0.3, 0.4]]})

    async with ollama_factory(handler) as client:
        assert await client.embed("embed", ["one", "two"], truncate=False) == [
            [0.1, 0.2],
            [0.3, 0.4],
        ]


@pytest.mark.parametrize(
    "payload",
    [
        {"embeddings": []},
        {"embeddings": [[0.1], [0.2, 0.3]]},
        {"embeddings": [[True]]},
        {"embeddings": [["bad"]]},
    ],
)
async def test_invalid_embeddings_are_rejected(ollama_factory, payload: dict) -> None:
    async with ollama_factory(lambda request: httpx.Response(200, json=payload)) as client:
        with pytest.raises(OllamaInvalidResponse):
            await client.embed("embed", "text")


async def test_non_finite_embedding_json_is_rejected(ollama_factory) -> None:
    async with ollama_factory(
        lambda request: httpx.Response(200, content=b'{"embeddings":[[NaN]]}')
    ) as client:
        with pytest.raises(OllamaInvalidResponse):
            await client.embed("embed", "text")


async def test_pull_streams_progress_with_long_read_timeout(ollama_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/pull"
        assert json.loads(request.content) == {"model": "chat:latest", "stream": True}
        assert request.extensions["timeout"]["read"] == 600
        return httpx.Response(
            200,
            content=b'{"status":"downloading","completed":1,"total":2}\n{"status":"success"}\n',
        )

    async with ollama_factory(handler) as client:
        progress = [item async for item in client.pull("chat:latest")]
    assert progress[-1] == {"status": "success"}


async def test_delete_is_backend_only_and_handles_missing_model(ollama_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/api/delete"
        assert json.loads(request.content) == {"model": "chat:latest"}
        return httpx.Response(200)

    async with ollama_factory(handler) as client:
        assert await client.delete("chat:latest") is None
    async with ollama_factory(
        lambda request: httpx.Response(404, json={"error": "not found"})
    ) as client:
        with pytest.raises(ModelNotFound):
            await client.delete("missing")


async def test_redirects_are_not_followed(ollama_factory) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"Location": "https://external.example/steal"})

    async with ollama_factory(handler) as client:
        assert client._client.trust_env is False
        with pytest.raises(OllamaError):
            await client.version()
    assert calls == 1


async def test_empty_inputs_are_rejected_before_network(ollama_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("network must not be called")

    async with ollama_factory(handler) as client:
        with pytest.raises(ValueError):
            await client.embed("embed", [])
        with pytest.raises(ValueError):
            _ = [chunk async for chunk in client.chat("chat", [])]
