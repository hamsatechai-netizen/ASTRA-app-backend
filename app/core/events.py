"""
Application lifespan.

Startup/shutdown hooks belong here, not scattered across `main.py`. Today
this only disposes the DB engine's connection pool on shutdown; future
phases can add startup checks (e.g. DB connectivity probe, cache warmup)
without touching the app factory.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.database.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Application startup: initializing resources.")
    yield
    logger.info("Application shutdown: releasing resources.")
    await engine.dispose()
