"""
Structured logging configuration (Loguru).

Replaces the standard library `logging` handlers (including Uvicorn's) with
an `InterceptHandler` that forwards everything into Loguru, so the whole
process — app code and the ASGI server — emits one consistent log format.
`LOG_JSON=true` switches to structured JSON output for production log
aggregation; local development gets a human-readable line format instead.
"""

import logging
import sys

from loguru import logger

from app.config.settings import get_settings

settings = get_settings()


class InterceptHandler(logging.Handler):
    """Redirects stdlib `logging` records into Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_back and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logging() -> None:
    """Configure Loguru sinks and redirect stdlib/Uvicorn logging into them. Call once at startup."""
    logger.remove()

    if settings.LOG_JSON:
        logger.add(sys.stdout, level=settings.LOG_LEVEL, serialize=True, backtrace=False, diagnose=False)
    else:
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS!UTC}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[request_id]}</cyan> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
        logger.configure(extra={"request_id": "-"})
        logger.add(sys.stdout, level=settings.LOG_LEVEL, format=log_format, backtrace=False, diagnose=False)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        std_logger = logging.getLogger(name)
        std_logger.handlers = [InterceptHandler()]
        std_logger.propagate = False

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
