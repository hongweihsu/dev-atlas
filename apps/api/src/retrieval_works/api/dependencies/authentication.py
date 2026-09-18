from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from retrieval_works.application.ports.authentication import (
    AuthenticatedPrincipal,
    InvalidCredentialError,
    TokenVerifier,
)
from retrieval_works.application.ports.workspace_access import (
    AuthorizedWorkspace,
    WorkspaceAccessRepository,
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_authenticated_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthenticatedPrincipal:
    verifier = cast(
        TokenVerifier | None, getattr(request.app.state, "token_verifier", None)
    )
    if verifier is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "authentication_unavailable",
                "message": "request authentication is not configured",
            },
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("a bearer token is required")
    try:
        return verifier.verify(credentials.credentials)
    except InvalidCredentialError as error:
        raise _unauthorized(str(error)) from error


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "invalid_credentials", "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


CurrentPrincipal = Annotated[
    AuthenticatedPrincipal, Depends(get_authenticated_principal)
]


async def get_authorized_workspace(
    request: Request,
    principal: CurrentPrincipal,
    workspace_id: Annotated[UUID, Header(alias="X-Workspace-ID")],
) -> AuthorizedWorkspace:
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
    workspace = await repository.resolve(principal, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "workspace_access_denied",
                "message": "the current user cannot access this workspace",
            },
        )
    return workspace


CurrentWorkspace = Annotated[AuthorizedWorkspace, Depends(get_authorized_workspace)]


def require_workspace_editor(workspace: CurrentWorkspace) -> AuthorizedWorkspace:
    if workspace.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "workspace_write_denied",
                "message": "viewer membership cannot modify workspace documents",
            },
        )
    return workspace


WritableWorkspace = Annotated[AuthorizedWorkspace, Depends(require_workspace_editor)]


def require_workspace_owner(workspace: CurrentWorkspace) -> AuthorizedWorkspace:
    if workspace.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "workspace_owner_required",
                "message": "workspace owner access is required",
            },
        )
    return workspace


OwnedWorkspace = Annotated[AuthorizedWorkspace, Depends(require_workspace_owner)]
