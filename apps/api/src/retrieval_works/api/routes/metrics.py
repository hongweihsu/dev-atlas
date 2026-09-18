import hmac

from fastapi import APIRouter, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from retrieval_works.core.config import Settings
from retrieval_works.infrastructure.observability import HttpMetrics

router = APIRouter(tags=["observability"])


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    settings: Settings = request.app.state.settings
    configured_token = settings.observability_metrics_token
    if configured_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Metrics endpoint is not configured.",
        )

    authorization = request.headers.get("authorization", "")
    scheme, _, supplied_token = authorization.partition(" ")
    if (
        scheme.lower() != "bearer"
        or not supplied_token
        or not hmac.compare_digest(
            supplied_token,
            configured_token.get_secret_value(),
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid metrics credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    http_metrics: HttpMetrics = request.app.state.http_metrics
    return Response(
        content=generate_latest(http_metrics.registry),
        media_type=CONTENT_TYPE_LATEST,
    )
