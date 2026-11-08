# Dependency license review — Phase 2

This is a pinned-build inventory, not legal advice or a complete appliance release clearance.
The production image installs only `backend/requirements.txt`; development tools are separate.

## Direct dependencies

| Package | Pinned version | Declared license |
|---|---:|---|
| FastAPI | 0.162.2 | MIT |
| Uvicorn | 0.54.0 | BSD-3-Clause |
| Pydantic | 2.14.3 | MIT |
| pydantic-settings | 2.16.2 | MIT |
| SQLAlchemy | 2.0.46 | MIT |
| aiosqlite | 0.22.1 | MIT |
| Alembic | 1.18.4 | MIT |
| httpx | 0.28.1 | BSD-3-Clause |
| structlog | 26.1.0 | MIT OR Apache-2.0 |

## Transitive policy exceptions requiring approval

No GPL or AGPL package is installed by this backend. However, the fixed stack also brings in
permissive licenses outside the four licenses explicitly named in the brief:

| Package | Version | License | Why present |
|---|---:|---|---|
| certifi | 2026.10.23 | MPL-2.0 | Mandatory httpx CA certificate bundle |
| greenlet | 3.5.6 | MIT AND PSF-2.0 | SQLAlchemy async support; includes PSF-licensed material |
| typing_extensions | 4.16.0 | PSF-2.0 | Required by Pydantic/SQLAlchemy typing |

MPL-2.0 is file-level weak copyleft; PSF-2.0 is permissive. They are not GPL/AGPL, but they
still need an explicit policy decision before commercial distribution. Removing their names
from a notice file would not remove the obligations. Preserve upstream license texts and
notices in the release bundle. The optional SearXNG AGPL exception remains a separate Phase 8
decision; SearXNG is not installed or started by this phase.

## Remaining runtime transitives

annotated-doc, annotated-types, anyio, h11, Mako, pydantic-core, pydantic-settings,
sniffio, typing-inspection: MIT or MIT/Apache dual licensed.
click, httpcore, idna, MarkupSafe, python-dotenv, starlette: BSD.
opentelemetry-api: Apache-2.0. It is a FastAPI dependency; no telemetry SDK, exporter,
instrumentation, or external telemetry endpoint is configured by this application.

## Development/build tools

pytest, pytest-asyncio, asgi-lifespan, ruff, iniconfig, pluggy, Pygments, packaging, and
setuptools use MIT, BSD, Apache-2.0, or dual permissive licenses. They are not copied into
the production image. The Python/Debian base image contains operating-system components
with their own licenses, including GPL components; final image-level redistribution review
and digest pinning remain Phase 10 work.

Before a commercial release: archive exact license texts, generate an image/package/model
SBOM, review modifications and attribution, and obtain approval for the exceptions above.
