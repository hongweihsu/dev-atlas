from datetime import datetime
from typing import cast

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from retrieval_works.infrastructure.authentication import DevelopmentSessionIssuer


class DevelopmentSessionResponse(BaseModel):
    access_token: str
    token_type: str
    workspace_id: str
    expires_at: datetime


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/development-session",
    response_model=DevelopmentSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_development_session(request: Request) -> DevelopmentSessionResponse:
    issuer = cast(
        DevelopmentSessionIssuer | None,
        getattr(request.app.state, "development_session_issuer", None),
    )
    if issuer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    session = issuer.issue()
    return DevelopmentSessionResponse(
        access_token=session.access_token,
        token_type="bearer",
        workspace_id=str(session.workspace_id),
        expires_at=session.expires_at,
    )
