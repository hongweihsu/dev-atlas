from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from devatlas.core.config import get_settings


def create_database_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)
