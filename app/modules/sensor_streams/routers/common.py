"""
Pieces shared by the ECG and ACC ingestion routers: rate limits, documented
error responses, and the OpenAPI request-body schema.

Rate limits — why these values
------------------------------
Every other route gets `RATE_LIMIT_DEFAULT` (60/minute) per client IP via
`SlowAPIMiddleware`. That is unsuitable here: a client uploading ECG or ACC
in 5–10 second batches sends 6–12 requests per minute per stream, so a few
athletes on one shared network (an academy's Wi-Fi) would exhaust a single
per-IP budget together. A route-level `@limiter.limit(...)` replaces the
default for these two routes only (the global default is unchanged) with:

- `PER_CALLER_LIMIT` per authenticated caller (`authenticated_caller_key`):
  120/minute — 10–20x normal batching, leaving room for a client draining
  a backlog after a reconnect (at most 5,000 samples per request).
- `PER_IP_LIMIT` per client IP: 1,200/minute — a ceiling for a whole
  shared network (on the order of 100 concurrently streaming athletes at
  ~12 requests/minute each).

Both are counted per route, so ECG and ACC each have their own budget.
Limits are only counted for requests that pass authentication and body
validation (slowapi's decorator runs after FastAPI resolves dependencies);
rejected requests never reach a database write.
"""

from typing import Any

from fastapi import status
from pydantic import BaseModel

from app.modules.sensor_streams.schemas import ErrorResponse

PER_CALLER_LIMIT = "120/minute"
PER_IP_LIMIT = "1200/minute"

SAMPLES_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "Missing, invalid, or expired access token.",
    },
    status.HTTP_403_FORBIDDEN: {
        "model": ErrorResponse,
        "description": "The session does not belong to the authenticated athlete.",
    },
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "No athlete profile exists for the authenticated account, or no session "
        "exists for sessionId.",
    },
    status.HTTP_409_CONFLICT: {
        "model": ErrorResponse,
        "description": "This batchId was already accepted for this session with different contents "
        "(BATCH_ID_REUSED). A genuine retry of the same batch returns 201 with `duplicate: true`.",
    },
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {
        "model": ErrorResponse,
        "description": "The request body exceeds the per-request byte limit.",
    },
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "model": ErrorResponse,
        "description": "The batch is empty/too large, sessionId/batchId is not a UUID, or a sample failed "
        "validation. Error details never echo sample values.",
    },
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "description": "Rate limit exceeded for this caller or network.",
    },
}


def _inline_refs(node: Any, defs: dict[str, Any]) -> Any:
    """Replace every local `#/$defs/...` reference with the referenced schema."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            return _inline_refs(defs[ref.removeprefix("#/$defs/")], defs)
        return {key: _inline_refs(value, defs) for key, value in node.items()}
    if isinstance(node, list):
        return [_inline_refs(item, defs) for item in node]
    return node


def request_body_openapi(model: type[BaseModel]) -> dict[str, Any]:
    """
    `openapi_extra` documenting `model` as the JSON request body.

    The body is parsed by `batch_body` (not a FastAPI body parameter), so
    FastAPI can't infer it; the schema is generated from the same Pydantic
    model, with nested definitions inlined so it resolves standalone.
    """
    schema = model.model_json_schema(by_alias=True)
    defs = schema.pop("$defs", {})
    return {
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _inline_refs(schema, defs)}},
        }
    }
