from typing import Literal, cast

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel

from devatlas.api.dependencies.authentication import CurrentPrincipal, CurrentWorkspace
from devatlas.application.ports.authentication import (
    InvalidCredentialError,
    TokenVerifier,
)
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
    request: Request,
    principal: CurrentPrincipal,
    identity_token: str | None = Header(default=None, alias="X-Identity-Token"),
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
    identity_verifier = cast(
        TokenVerifier | None,
        getattr(request.app.state, "identity_token_verifier", None),
    )
    if identity_verifier is not None:
        if identity_token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "identity_token_required",
                    "message": "an identity token is required",
                },
            )
        try:
            identity = identity_verifier.verify(identity_token)
        except InvalidCredentialError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "invalid_identity_token", "message": str(error)},
            ) from error
        if (identity.issuer, identity.subject) != (principal.issuer, principal.subject):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "identity_mismatch",
                    "message": "access and identity token subjects differ",
                },
            )
        principal = identity
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
