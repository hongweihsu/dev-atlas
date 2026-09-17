from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from devatlas.api.dependencies.authentication import CurrentPrincipal, OwnedWorkspace
from devatlas.application.ports.workspace_access import (
    AuthorizedWorkspace,
    WorkspaceAccessRepository,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceResponse(BaseModel):
    user_id: str
    workspace_id: str
    workspace_name: str
    role: Literal["owner", "editor", "viewer"]


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("workspace name cannot be blank")
        return normalized


class CreateInvitationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: Literal["editor", "viewer"]

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        local, separator, domain = normalized.partition("@")
        if not separator or not local or "." not in domain:
            raise ValueError("a valid email address is required")
        return normalized


class InvitationResponse(BaseModel):
    invitation_id: str
    token: str
    workspace_name: str
    email: str
    role: Literal["editor", "viewer"]


class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=20, max_length=255)


def _repository(request: Request) -> WorkspaceAccessRepository:
    repository = cast(
        WorkspaceAccessRepository | None,
        getattr(request.app.state, "workspace_access_repository", None),
    )
    if repository is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "authorization_unavailable",
                "message": "workspace authorization is not configured",
            },
        )
    return repository


def _response(workspace: AuthorizedWorkspace) -> WorkspaceResponse:
    return WorkspaceResponse(
        user_id=str(workspace.user_id),
        workspace_id=str(workspace.workspace_id),
        workspace_name=workspace.workspace_name,
        role=workspace.role,
    )


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    request: Request, principal: CurrentPrincipal
) -> list[WorkspaceResponse]:
    return [
        _response(item)
        for item in await _repository(request).list_for_principal(principal)
    ]


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    body: CreateWorkspaceRequest, request: Request, principal: CurrentPrincipal
) -> WorkspaceResponse:
    return _response(await _repository(request).create_workspace(principal, body.name))


@router.post(
    "/{target_workspace_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    target_workspace_id: UUID,
    body: CreateInvitationRequest,
    request: Request,
    workspace: OwnedWorkspace,
) -> InvitationResponse:
    if workspace.workspace_id != target_workspace_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "code": "workspace_access_denied",
                "message": "workspace header and path differ",
            },
        )
    result = await _repository(request).create_invitation(
        workspace, body.email, body.role
    )
    return InvitationResponse(
        invitation_id=str(result.invitation_id),
        token=result.token,
        workspace_name=result.workspace_name,
        email=result.email,
        role=cast(Literal["editor", "viewer"], result.role),
    )


@router.post("/invitations/accept", response_model=WorkspaceResponse)
async def accept_invitation(
    body: AcceptInvitationRequest, request: Request, principal: CurrentPrincipal
) -> WorkspaceResponse:
    try:
        return _response(
            await _repository(request).accept_invitation(principal, body.token)
        )
    except PermissionError as error:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "invitation_email_mismatch", "message": str(error)},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "invalid_invitation", "message": str(error)},
        ) from error
