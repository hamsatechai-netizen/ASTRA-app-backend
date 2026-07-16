"""
Blocks until PostgreSQL accepts connections.

Used as an entrypoint guard in orchestration environments (Docker Compose,
Kubernetes init containers) so the API process doesn't start racing the
database's own startup.
"""
import asyncio
import sys

from sqlalchemy.ext.asyncio import create_async_engine

from app.config.settings import get_settings

MAX_ATTEMPTS = 30
DELAY_SECONDS = 1.0


async def wait_for_db() -> None:
    settings = get_settings()
    engine = create_async_engine(str(settings.DATABASE_URL))

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            async with engine.connect():
                print(f"Database is ready (attempt {attempt}/{MAX_ATTEMPTS}).")
                return
        except Exception as exc:  # noqa: BLE001 - intentional broad catch while polling
            print(f"Database not ready (attempt {attempt}/{MAX_ATTEMPTS}): {exc}")
            await asyncio.sleep(DELAY_SECONDS)
        finally:
            await engine.dispose()

    print("Database did not become ready in time.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(wait_for_db())
