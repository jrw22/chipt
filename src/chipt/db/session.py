"""Async SQLAlchemy engine (Core only, no ORM)."""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from chipt.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


async def get_conn() -> AsyncIterator[AsyncConnection]:
    """FastAPI dependency: one transaction per request."""
    async with get_engine().begin() as conn:
        yield conn
