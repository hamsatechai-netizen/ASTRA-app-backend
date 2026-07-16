"""
Centralized exception handling.

Registered once, in `main.py`, via `register_exception_handlers(app)`. This
guarantees every error path — expected (`AppException`), validation
(`RequestValidationError`), HTTP (`StarletteHTTPException`), and unexpected
(`Exception`) — returns the same `ErrorResponse` envelope and is logged
consistently, instead of leaking stack traces or framework-default bodies.
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.responses import ErrorDetail, ErrorResponse
from app.exceptions.base import AppException


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = _request_id(request)
    logger.bind(request_id=request_id).warning("{}: {}", exc.error_code, exc.message)
    payload = ErrorResponse(
        error=ErrorDetail(code=exc.error_code, message=exc.message, details=exc.details),
        request_id=request_id,
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = _request_id(request)
    logger.bind(request_id=request_id).info("Request validation failed: {}", exc.errors())
    payload = ErrorResponse(
        error=ErrorDetail(
            code="VALIDATION_ERROR", message="Request validation failed.", details=exc.errors()
        ),
        request_id=request_id,
    )
    content = payload.model_dump(mode="json")
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=content)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = _request_id(request)
    logger.bind(request_id=request_id).warning("HTTP {}: {}", exc.status_code, exc.detail)
    payload = ErrorResponse(
        error=ErrorDetail(code="HTTP_ERROR", message=str(exc.detail)),
        request_id=request_id,
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id(request)
    logger.bind(request_id=request_id).exception("Unhandled exception occurred.")
    payload = ErrorResponse(
        error=ErrorDetail(code="INTERNAL_SERVER_ERROR", message="An unexpected error occurred."),
        request_id=request_id,
    )
    content = payload.model_dump(mode="json")
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=content)


def register_exception_handlers(app: FastAPI) -> None:
    """Wire every exception handler onto the FastAPI app instance."""
    # Starlette's `add_exception_handler` is typed to accept only
    # `Callable[[Request, Exception], ...]`, so handlers narrowed to a
    # specific exception subclass (the correct, precise signature for each
    # of these) trip mypy's argument variance check. This is a well-known
    # stub limitation, not a real type error — FastAPI's own docs use the
    # same pattern.
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
