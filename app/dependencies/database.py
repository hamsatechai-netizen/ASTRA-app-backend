"""
Per-request database session dependency.

Yields one `AsyncSession` per request, commits on clean completion, and
rolls back on any exception — routes/services never manage transactions
themselves.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionFactory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
