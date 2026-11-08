"""Create the schema and seed the single MVP athlete. Usage: `uv run chipt-initdb`."""

import asyncio
from pathlib import Path

from sqlalchemy import text

from chipt.config import get_settings
from chipt.db.session import get_engine

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


async def init_db() -> None:
    settings = get_settings()
    engine = get_engine()
    async with engine.begin() as conn:
        raw = await conn.get_raw_connection()
        # asyncpg can execute a multi-statement script directly.
        await raw.driver_connection.execute(SCHEMA_PATH.read_text())
        await conn.execute(
            text(
                "INSERT INTO athlete (id, display_name) VALUES (:id, :name) "
                "ON CONFLICT (id) DO UPDATE SET display_name = EXCLUDED.display_name"
            ),
            {"id": settings.default_athlete_id, "name": settings.default_athlete_display_name},
        )
        await conn.execute(
            text("SELECT setval('athlete_id_seq', GREATEST((SELECT max(id) FROM athlete), 1))")
        )
    await engine.dispose()
    print("Schema applied; default athlete seeded.")


def main() -> None:
    asyncio.run(init_db())


if __name__ == "__main__":
    main()
