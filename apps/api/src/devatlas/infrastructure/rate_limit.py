from hashlib import sha256
from inspect import isawaitable
from typing import Any, cast

from arq.connections import ArqRedis


class RateLimitExceededError(RuntimeError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("mutation rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


_FIXED_WINDOW_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


class RedisMutationRateLimiter:
    """Shared fixed-window limiter for costly or abuse-prone mutations."""

    def __init__(self, redis: ArqRedis, *, namespace: str = "devatlas") -> None:
        self._redis = redis
        self._namespace = namespace

    async def check(
        self,
        *,
        identity: str,
        action: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        identity_hash = sha256(identity.encode("utf-8")).hexdigest()
        key = f"{self._namespace}:rate-limit:{action}:{identity_hash}"
        evaluation = self._redis.eval(_FIXED_WINDOW_SCRIPT, 1, key, str(window_seconds))
        resolved: Any = await evaluation if isawaitable(evaluation) else evaluation
        result = cast(list[int], resolved)
        count, ttl = int(result[0]), int(result[1])
        if count > limit:
            raise RateLimitExceededError(max(ttl, 1))
