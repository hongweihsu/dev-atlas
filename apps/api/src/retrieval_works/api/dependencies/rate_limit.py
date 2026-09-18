from typing import cast

from fastapi import HTTPException, Request, status

from retrieval_works.infrastructure.rate_limit import (
    RateLimitExceededError,
    RedisMutationRateLimiter,
)


async def enforce_mutation_rate_limit(
    request: Request,
    *,
    identity: str,
    action: str,
    limit: int,
) -> None:
    limiter = cast(
        RedisMutationRateLimiter | None,
        getattr(request.app.state, "mutation_rate_limiter", None),
    )
    if limiter is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "rate_limiter_unavailable",
                "message": "mutation rate limiting is not configured",
            },
        )
    settings = request.app.state.settings
    try:
        await limiter.check(
            identity=identity,
            action=action,
            limit=limit,
            window_seconds=settings.mutation_rate_window_seconds,
        )
    except RateLimitExceededError as error:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "rate_limit_exceeded",
                "message": "too many requests; try again later",
            },
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from error
