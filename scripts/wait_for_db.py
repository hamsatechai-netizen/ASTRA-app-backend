"""
Blocks until the Supabase PostgreSQL database accepts connections.

Used as an entrypoint guard in orchestration environments (Docker Compose,
Kubernetes init containers) so the API process doesn't start racing a
transient network issue or a paused/waking Supabase project.
"""

import asyncio
import sys

from app.config.settings import get_settings
from app.database.session import build_connect_args
from sqlalchemy.ext.asyncio import create_async_engine

MAX_ATTEMPTS = 30
DELAY_SECONDS = 1.0


async def wait_for_db() -> None:
    settings = get_settings()
    engine = create_async_engine(str(settings.DATABASE_URL), connect_args=build_connect_args(settings))

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
