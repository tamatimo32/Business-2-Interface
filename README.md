# Business-2-Interface

A configurable, offline-first web chat application for a local Ollama appliance.
The repository name is not the product name; configure `PRODUCT_NAME` in `.env`.

## Current status

**Phase 2: backend foundation.** This repository currently provides configuration,
the complete planned SQL schema and initial migration, async SQLite infrastructure,
a shared async Ollama client, structured logging, consistent errors, health endpoints,
a non-root Docker image, and mocked automated tests.

Authentication, chat/SSE routes, the frontend, document ingestion, web search, and
administration are later phases. Health endpoints are intentionally public and are
not protected by Ollama authentication (Ollama itself has none). Production exposure
will be restricted to the HTTPS reverse-proxy entry point in the deployment phase.

## Backend

### Requirements

- Python 3.11 or newer (the pinned dependency set is tested on Python 3.11).
- Ollama running locally for a live connection check. Tests do **not** require Ollama.
- No model is downloaded automatically. `qwen2.5:7b` is a configurable candidate,
  not a claim that every hardware profile or model variant is suitable/approved.

### Run locally with Ollama on your machine

From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
python -m pip install -e backend --no-deps
cp .env.example .env
cd backend
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log --reload
```

On Windows, create the environment with `py -3.11 -m venv .venv` and activate with
`.venv\Scripts\Activate.ps1`; run the same Python/Alembic/Uvicorn commands afterward.

The root `.env` is loaded even when working inside `backend/`. Environment variables
override it. `DATA_DIR=./data` resolves to the repository's ignored `data/` directory.
Startup verifies the database and Alembic revision; it does not silently create tables
with `create_all`. Run migrations explicitly before local startup. Use one worker.

If Ollama is not already running, start it using your installed Ollama application or
`ollama serve`. Installing a model is an explicit operator action, for example:

```bash
ollama pull qwen2.5:7b
```

That pull uses the internet. Core application startup and health checks do not pull models.

### Verify with curl

Application health:

```bash
curl -fsS http://127.0.0.1:8000/api/health
```

Expected:

```json
{"status":"ok","version":"0.1.0"}
```

Backend-mediated Ollama health:

```bash
curl -fsS http://127.0.0.1:8000/api/health/ollama
```

Expected when Ollama is running (model count depends on your installation):

```json
{"reachable":true,"version":"YOUR_OLLAMA_VERSION","model_count":1}
```

If Ollama cannot be connected to, this diagnostic endpoint returns HTTP 200 with:

```json
{"reachable":false,"version":null,"model_count":null}
```

Monitor the `reachable` field, not just the HTTP status. Invalid upstream responses and
other upstream failures use the common error envelope with HTTP 502.

Operator-only direct diagnostics on the appliance host:

```bash
curl -fsS http://127.0.0.1:11434/api/version
curl -fsS http://127.0.0.1:11434/api/tags
```

These direct commands are for the operator. Browser code must never call Ollama directly.

### Run tests and checks

From the repository root, with the environment activated:

```bash
cd backend
python -m pytest -q
ruff check app tests migrations
ruff format --check app tests migrations
alembic upgrade head
alembic check
```

Tests use temporary SQLite databases and `httpx.MockTransport`; they never contact a
real Ollama server or the internet. Database tests exercise migrations, WAL/foreign-key
PRAGMAs on new connections, ownership constraints, and migration/model agreement.

Useful migration commands, from `backend/`:

```bash
alembic current
alembic history
alembic upgrade head
alembic upgrade head --sql
```

`alembic downgrade base` drops all application tables and is destructive. Test it only
against a disposable database. The automated tests perform a round trip on temporary data.

### Build the backend image

From the repository root:

```bash
docker build -f backend/Dockerfile -t local-ai-backend:0.1.0 .
docker run --rm --name local-ai-backend \
  -p 127.0.0.1:8000:8000 \
  -v local-ai-data:/data \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  local-ai-backend:0.1.0
```

The image uses a slim Python base, a fixed non-root UID/GID, runtime-only pinned
dependencies, and a persistent `/data` volume. It binds to `0.0.0.0` inside the container;
the example publishes only to the host's loopback. It applies migrations at startup.
Do not mount the development `.env` over the production defaults. Caddy, internal Docker
networks, image digest pinning, and appliance packaging arrive in Phase 10.

### Configuration and privacy

Every supported environment variable is documented in [`.env.example`](.env.example).
Infrastructure settings are environment-driven; future admin overrides will be explicit.
Reserved settings are validated but do not imply that later-phase features already exist.

Logs are JSON and contain request IDs, route templates, statuses, timings, and safe error
classes. They do not log request bodies, prompts, completions, headers, query strings,
passwords, cookies, or raw upstream exception text. Uvicorn's raw access log is disabled.

All API failures use:

```json
{"error":{"code":"not_found","message":"Not Found"}}
```

CORS is enabled only in `APP_ENV=development`, for the exact configured Vite origins.
Production has no CORS middleware. Development exposes local OpenAPI JSON at
`/openapi.json`; interactive docs are disabled until their assets can be bundled locally.
Production serves neither docs nor an OpenAPI schema. No CDN assets are used.

### Ollama service interface

`app.services.ollama.OllamaClient` owns one shared `httpx.AsyncClient` per application
process and provides `version`, `list_models`, `running_models`, `show_model`, streaming
`chat`, `embed`, streaming `pull`, and `delete`. Chat/pull yield parsed upstream NDJSON;
translation to the planned browser SSE contract happens in Phase 4. Pull/delete have no
browser routes. Redirects and environment proxies are disabled.

### Licensing and current limitations

See [`docs/LICENSE_REVIEW.md`](docs/LICENSE_REVIEW.md). No GPL/AGPL Python package is
introduced. The fixed stack nevertheless requires policy approval for transitive
`certifi` (MPL-2.0), `greenlet` (MIT AND PSF-2.0), and `typing_extensions` (PSF-2.0).
SearXNG's AGPL exception remains unused and unapproved.

This phase does not provide login, authorization, chat endpoints, or a production HTTPS
boundary. Do not expose it directly to an untrusted network. The planned schema exists,
but later-phase services/workers are not active. The container base tag still needs a
verified digest and OS-level license/SBOM review before appliance distribution.
