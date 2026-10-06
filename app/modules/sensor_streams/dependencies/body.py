"""
Size-capped, payload-safe JSON body parsing for ECG/ACC sample batches.

These endpoints parse their body here instead of declaring it as an
ordinary FastAPI body parameter, for two reasons specific to high-volume
sensor batches:

1. **Byte limit.** The app has no request-body size limit, and Pydantic's
   `max_length` on `samples` only applies *after* the whole body has been
   read and decoded. Here the body is read incrementally and rejected
   (413) as soon as it exceeds `MAX_BODY_BYTES` — whether or not the client
   sent an honest `Content-Length`.
2. **No payload echo.** The global `RequestValidationError` handler logs
   and returns `exc.errors()`, and Pydantic includes each failing `input`
   in those errors — for an oversized batch that `input` is the entire
   sample list. Validation failures here are re-raised as
   `ValidationException` with only `loc`/`msg`/`type` per error, so raw
   sample data is never logged or reflected back. The response keeps the
   same `ErrorResponse` envelope and `VALIDATION_ERROR` code (422).
"""

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from fastapi import Request
from pydantic import BaseModel, ValidationError

from app.modules.sensor_streams.exceptions import PayloadTooLargeException, ValidationException

# A full 5,000-sample ACC batch (the larger of the two sample shapes, with
# camelCase keys and full ISO 8601 timestamps) serializes to roughly 0.5 MB;
# 1 MiB leaves headroom for formatting without allowing unbounded bodies.
MAX_BODY_BYTES = 1024 * 1024

ModelT = TypeVar("ModelT", bound=BaseModel)


def _sanitized_errors(exc: ValidationError) -> list[dict[str, Any]]:
    """Strip `input`/`ctx`/`url` from Pydantic errors so no sample values are logged or echoed."""
    return [
        {"loc": ["body", *error["loc"]], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors(include_url=False, include_context=False, include_input=False)
    ]


async def _read_capped_body(request: Request) -> bytes:
    declared_length = request.headers.get("content-length")
    if declared_length is not None and declared_length.isdigit() and int(declared_length) > MAX_BODY_BYTES:
        raise PayloadTooLargeException(f"The request body must not exceed {MAX_BODY_BYTES} bytes.")

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            raise PayloadTooLargeException(f"The request body must not exceed {MAX_BODY_BYTES} bytes.")
    return bytes(body)


def batch_body(model: type[ModelT]) -> Callable[[Request], Awaitable[ModelT]]:
    """Build a `Depends()`-compatible provider that reads, size-checks and validates a `model` JSON body."""

    async def parse(request: Request) -> ModelT:
        raw = await _read_capped_body(request)
        try:
            return model.model_validate_json(raw)
        except ValidationError as exc:
            raise ValidationException("Request validation failed.", details=_sanitized_errors(exc)) from None

    return parse
