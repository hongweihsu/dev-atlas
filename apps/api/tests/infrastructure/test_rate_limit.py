from typing import Any, cast

import pytest
from arq.connections import ArqRedis

from retrieval_works.infrastructure.rate_limit import (
    RateLimitExceededError,
    RedisMutationRateLimiter,
)


class FakeRedis:
    def __init__(self, results: list[list[int]]) -> None:
        self.results = results
        self.keys: list[str] = []

    async def eval(self, script: str, numkeys: int, *keys_and_args: str) -> list[int]:
        self.keys.append(keys_and_args[0])
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_rate_limiter_hashes_identity_and_allows_within_limit() -> None:
    redis = FakeRedis([[1, 3600]])
    limiter = RedisMutationRateLimiter(cast(ArqRedis, cast(Any, redis)))

    await limiter.check(
        identity="issuer:sensitive-subject",
        action="workspace-create",
        limit=1,
        window_seconds=3600,
    )

    assert "sensitive-subject" not in redis.keys[0]
    assert redis.keys[0].startswith("retrieval_works:rate-limit:workspace-create:")


@pytest.mark.asyncio
async def test_rate_limiter_reports_redis_ttl_after_limit() -> None:
    redis = FakeRedis([[6, 137]])
    limiter = RedisMutationRateLimiter(cast(ArqRedis, cast(Any, redis)))

    with pytest.raises(RateLimitExceededError) as captured:
        await limiter.check(
            identity="issuer:subject",
            action="workspace-create",
            limit=5,
            window_seconds=3600,
        )

    assert captured.value.retry_after_seconds == 137
