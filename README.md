# ASTRA Backend

Production-grade FastAPI backend, built on Enterprise Clean Architecture.

> **Phase 1 status**: architecture, configuration, and project scaffold only.
> No business logic, endpoints, or persistence models exist yet — see
> [Future Features](#future-features) and `docs/architecture.md`.

## Tech stack

| Concern         | Choice                                  |
|-----------------|------------------------------------------|
| Language        | Python 3.12+                             |
| Framework       | FastAPI                                  |
| Validation      | Pydantic v2 / pydantic-settings          |
| ORM             | SQLAlchemy 2.x (async, asyncpg driver)   |
| Migrations      | Alembic                                  |
| Database        | PostgreSQL                               |
| Server          | Uvicorn (dev) / Gunicorn + Uvicorn workers (prod) |
| Logging         | Loguru (structured, JSON-capable)        |
| Testing         | Pytest + httpx + pytest-asyncio          |
| Rate limiting   | slowapi                                  |

## Getting started

```bash
# 1. Create and activate a virtualenv
python3.12 -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
make install-dev

# 3. Configure environment
cp .env.example .env
# edit .env — at minimum set SECRET_KEY and DATABASE_URL

# 4. Start PostgreSQL (or point DATABASE_URL at an existing instance)
docker compose up -d db

# 5. Run the app
make dev          # http://localhost:8000/docs
```

Or run everything (API + PostgreSQL) in containers:

```bash
cp .env.example .env
make docker-up
```

### Common commands

| Command              | Purpose                                         |
|----------------------|--------------------------------------------------|
| `make dev`           | Run the API with auto-reload                     |
| `make test`          | Run the test suite with coverage                 |
| `make lint`          | Ruff static analysis                              |
| `make format`        | Black + Ruff autofix                              |
| `make typecheck`     | mypy strict type checking                         |
| `make migrate-generate m="message"` | Autogenerate an Alembic migration  |
| `make migrate`       | Apply migrations                                  |
| `make docker-up`     | Build and run API + PostgreSQL via Compose        |

## API documentation

Once running:

- Swagger UI → `/docs`
- ReDoc → `/redoc`
- OpenAPI schema → `/openapi.json`

## Project structure

```
app/
├── main.py             Composition root — builds the FastAPI app instance.
├── api/v1/              Presentation layer: versioned routers only, no logic.
├── core/                Bootstrap: logging configuration, app lifespan events.
├── config/               Environment-driven settings (pydantic-settings).
├── database/            SQLAlchemy async engine, session factory, declarative Base.
├── models/               ORM models + shared mixins (UUID PK, UTC timestamps).
├── schemas/              Pydantic request/response DTOs.
├── repositories/         Repository Pattern: data-access abstractions over the ORM.
├── services/            Service layer: business/use-case orchestration.
├── dependencies/         FastAPI DI providers (DB session, pagination, etc).
├── middleware/           ASGI middleware: request ID, access logging, security headers.
├── security/            Security policy objects (rate limiter, future auth utilities).
├── validators/           Shared, reusable Pydantic field validators.
├── exceptions/           AppException hierarchy + centralized exception handlers.
├── utils/                Small stateless helpers (UTC time, UUID generation).
├── constants/            Fixed, non-configurable values and enums.
└── common/               Cross-cutting shared building blocks (response envelopes, enums).

tests/                   Pytest suite (unit/ + integration/), fixtures in conftest.py.
migrations/               Alembic environment and version scripts.
docs/                     Architecture documentation.
scripts/                  Operational helper scripts (e.g. wait_for_db.py).
```

See `docs/architecture.md` for the rationale behind every layer and the
request lifecycle through the middleware/exception stack.

## Architecture principles

- **Clean Architecture**: presentation (`api/`) → application (`services/`) →
  domain (`models/`, `schemas/`) → infrastructure (`database/`, `repositories/`).
  Dependencies always point inward; routes never touch the ORM directly.
- **Repository Pattern + Service Layer**: `repositories/base.py` and
  `services/base.py` define the contracts every feature module will
  implement, keeping query logic out of business logic and business logic
  out of routes.
- **Dependency Injection**: FastAPI's `Depends` system, wired through
  `dependencies/`, is the DI mechanism — no bespoke container.
- **Configuration-driven**: every environment-specific value lives in
  `config/settings.py` and is sourced from the environment; nothing is
  hardcoded, and required secrets have no default (fail-fast on missing config).
- **Security by default**: UUID identifiers, UTC timestamps, centralized
  exception handling (no leaked stack traces), CORS + trusted-host +
  security-header middleware, rate-limiting infrastructure, and
  correlation-ID request tracing are all wired in from day one.

## Future features

The following will be implemented in subsequent phases, on top of this
scaffold, without restructuring it:

- Send OTP / Verify OTP
- Existing user detection
- New user registration
- Athlete creation & onboarding
- Home dashboard
- Profile management

## Testing

```bash
make test
```

Phase 1 ships bootstrap smoke tests only (`tests/unit/test_app_bootstrap.py`)
that verify the app factory, Swagger/OpenAPI, and the middleware/exception
architecture — there is no business logic yet to test.
