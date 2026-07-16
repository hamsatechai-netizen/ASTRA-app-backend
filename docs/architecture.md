# Architecture

## Layering

This backend follows Enterprise Clean Architecture: dependencies point
inward, and each layer only knows about the layer(s) directly beneath it.

```
┌─────────────────────────────────────────────────────────────┐
│ Presentation        app/api/v1/                              │
│   Routers only. Parses/validates HTTP input (via schemas),   │
│   delegates to a service, returns a response envelope.       │
│   Never contains business logic or SQL.                      │
├─────────────────────────────────────────────────────────────┤
│ Application         app/services/                             │
│   Use-case orchestration and business rules. Depends on      │
│   repository *interfaces*, not on SQLAlchemy or FastAPI.     │
├─────────────────────────────────────────────────────────────┤
│ Domain              app/models/, app/schemas/                 │
│   ORM entities (models/) and DTOs (schemas/) — the shapes     │
│   of data, independent of how they're transported or stored. │
├─────────────────────────────────────────────────────────────┤
│ Infrastructure       app/repositories/, app/database/          │
│   Repository implementations talk to the DB via SQLAlchemy.  │
│   database/ owns the engine/session lifecycle.                │
└─────────────────────────────────────────────────────────────┘
```

Cross-cutting concerns that don't belong to a single layer live beside
these: `core/` (bootstrap), `middleware/` (ASGI), `security/` (policy),
`exceptions/` (error contract), `config/` (settings), `dependencies/` (DI
wiring), `constants/` / `common/` / `utils/` (shared primitives).

## Request lifecycle

```
Client
  │
  ▼
CORSMiddleware              — allowed origins from settings
  │
TrustedHostMiddleware        — rejects requests with an unexpected Host header
  │
SecurityHeadersMiddleware    — stamps HSTS / X-Frame-Options / etc. on the response
  │
LoggingMiddleware            — structured access-log line with timing + status
  │
RequestContextMiddleware     — assigns/propagates X-Request-ID, binds it to logs
  │
SlowAPIMiddleware            — enforces the default rate limit
  │
▼
FastAPI routing (app/api/v1/router.py)
  │
▼
Route handler → Service (business logic) → Repository (persistence)
  │
▼
Response, wrapped in SuccessResponse / PaginatedResponse (app/common/responses.py)
```

If anything raises, one of the four handlers registered in
`app/exceptions/handlers.py` catches it and returns a consistent
`ErrorResponse` — callers never see a raw traceback or an
inconsistently-shaped error body, and every error is logged with its
correlation ID.

## Why these choices

- **UUID primary keys, not auto-increment ints** (`models/base.py`):
  IDs are unguessable and safe to expose in URLs; they also allow client-
  or service-generated IDs without a round-trip to the DB.
- **UTC-only timestamps** (`utils/datetime.py`, `models/base.py`):
  avoids an entire class of timezone bugs; conversion to local time is a
  presentation concern, not a storage concern.
- **`AppException` hierarchy instead of raising `HTTPException` from
  services**: keeps the service layer framework-agnostic (a service
  shouldn't need to know what an HTTP status code is) while still mapping
  cleanly to one at the edge.
- **Repository Pattern**: without it, swapping an ORM, adding a cache, or
  unit-testing a service would require mocking SQLAlchemy internals.
  With it, tests can inject a fake repository implementing the same
  `BaseRepository` contract.
- **`lru_cache`-d settings**: environment parsing happens once per
  process; `Settings()` validation runs at import time, so a
  misconfigured deployment (missing `SECRET_KEY`/`DATABASE_URL`) fails at
  startup, not on the first request that happens to need it.
- **Async SQLAlchemy + asyncpg**: matches FastAPI's async request model
  end-to-end — no thread-pool bridging for DB calls.
- **slowapi for rate limiting**: gives every future endpoint a
  `@limiter.limit(...)` decorator for free; OTP send/verify (the most
  abuse-prone future endpoints) will lean on this heavily.

## Adding a new feature (future phases)

A typical feature (e.g. "Send OTP") will touch, in order:

1. `app/models/` — new ORM model (composing `UUIDMixin` + `TimestampMixin`).
2. `migrations/` — `make migrate-generate m="add otp table"`.
3. `app/schemas/` — request/response DTOs (extending `BaseSchema`).
4. `app/repositories/` — a concrete repository implementing `BaseRepository`.
5. `app/services/` — business logic, extending `BaseService`, raising
   `AppException` subclasses on failure.
6. `app/dependencies/` — a provider wiring the service (with its
   repository and DB session) for injection.
7. `app/api/v1/endpoints/` (new) — a thin router calling the service,
   registered onto `api_router` in `app/api/v1/router.py`.

No existing file needs restructuring to support this — it's additive.
