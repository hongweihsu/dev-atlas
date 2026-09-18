from dataclasses import dataclass
from inspect import isawaitable
from typing import Any

from arq.connections import ArqRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    database: bool
    redis: bool

    @property
    def ready(self) -> bool:
        return self.database and self.redis


class DependencyReadinessChecker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redis: ArqRedis,
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis

    async def check(self) -> ReadinessResult:
        database_ready = await self._database_is_ready()
        redis_ready = await self._redis_is_ready()
        return ReadinessResult(database=database_ready, redis=redis_ready)

    async def _database_is_ready(self) -> bool:
        try:
            async with self._session_factory() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def _redis_is_ready(self) -> bool:
        try:
            result: Any = self._redis.ping()
            resolved = await result if isawaitable(result) else result
            return bool(resolved)
        except Exception:
            return False
