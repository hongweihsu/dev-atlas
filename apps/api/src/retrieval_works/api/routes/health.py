from typing import Literal, cast

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from retrieval_works.infrastructure.readiness import DependencyReadinessChecker


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="retrieval-works-api")


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    database: Literal["ok", "unavailable"]
    redis: Literal["ok", "unavailable"]


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(request: Request, response: Response) -> ReadinessResponse:
    checker = cast(
        DependencyReadinessChecker | None,
        getattr(request.app.state, "readiness_checker", None),
    )
    if checker is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "readiness_unavailable",
                "message": "dependency readiness checks are not configured",
            },
        )
    result = await checker.check()
    if not result.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if result.ready else "not_ready",
        database="ok" if result.database else "unavailable",
        redis="ok" if result.redis else "unavailable",
    )
