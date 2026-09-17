from typing import Literal, cast

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from devatlas.api.dependencies.authentication import CurrentPrincipal, CurrentWorkspace
from devatlas.application.ports.workspace_access import (
    AuthorizedWorkspace,
    WorkspaceAccessRepository,
)


class SessionResponse(BaseModel):
    user_id: str
    workspace_id: str
    workspace_name: str
    role: Literal["owner", "editor", "viewer"]


router = APIRouter(prefix="/session", tags=["session"])


@router.post("/bootstrap", response_model=SessionResponse)
async def bootstrap_session(
    request: Request, principal: CurrentPrincipal
) -> SessionResponse:
    repository = cast(
        WorkspaceAccessRepository | None,
        getattr(request.app.state, "workspace_access_repository", None),
    )
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "authorization_unavailable",
                "message": "workspace authorization is not configured",
            },
        )
    workspace = await repository.bootstrap_personal_workspace(principal)
    return _session_response(workspace)


@router.get("", response_model=SessionResponse)
async def get_session(workspace: CurrentWorkspace) -> SessionResponse:
    return _session_response(workspace)


def _session_response(workspace: AuthorizedWorkspace) -> SessionResponse:
    return SessionResponse(
        user_id=str(workspace.user_id),
        workspace_id=str(workspace.workspace_id),
        workspace_name=workspace.workspace_name,
        role=workspace.role,
    )
