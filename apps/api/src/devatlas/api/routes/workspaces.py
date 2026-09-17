from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from devatlas.api.dependencies.authentication import CurrentPrincipal, OwnedWorkspace
from devatlas.api.dependencies.rate_limit import enforce_mutation_rate_limit
from devatlas.application.ports.workspace_access import (
    AuthorizedWorkspace,
    WorkspaceAccessRepository,
    WorkspaceMember,
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


class WorkspaceMemberResponse(BaseModel):
    user_id: str
    email: str | None
    display_name: str | None
    role: Literal["owner", "editor", "viewer"]
    joined_at: datetime


class UpdateMemberRoleRequest(BaseModel):
    role: Literal["editor", "viewer"]


class InvitationSummaryResponse(BaseModel):
    invitation_id: str
    email: str
    role: Literal["editor", "viewer"]
    status: Literal["pending", "accepted", "expired"]
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


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


def _require_matching_workspace(
    target_workspace_id: UUID, workspace: AuthorizedWorkspace
) -> None:
    if workspace.workspace_id != target_workspace_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "code": "workspace_access_denied",
                "message": "workspace header and path differ",
            },
        )


def _member_response(member: WorkspaceMember) -> WorkspaceMemberResponse:
    return WorkspaceMemberResponse(
        user_id=str(member.user_id),
        email=member.email,
        display_name=member.display_name,
        role=member.role,
        joined_at=member.joined_at,
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
    settings = request.app.state.settings
    await enforce_mutation_rate_limit(
        request,
        identity=f"{principal.issuer}:{principal.subject}",
        action="workspace-create",
        limit=settings.workspace_create_rate_limit,
    )
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
    _require_matching_workspace(target_workspace_id, workspace)
    settings = request.app.state.settings
    await enforce_mutation_rate_limit(
        request,
        identity=str(workspace.user_id),
        action="invitation-create",
        limit=settings.invitation_create_rate_limit,
    )
    try:
        result = await _repository(request).create_invitation(
            workspace, body.email, body.role
        )
    except ValueError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "invitation_conflict", "message": str(error)},
        ) from error
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


@router.get(
    "/{target_workspace_id}/members", response_model=list[WorkspaceMemberResponse]
)
async def list_members(
    target_workspace_id: UUID, request: Request, workspace: OwnedWorkspace
) -> list[WorkspaceMemberResponse]:
    _require_matching_workspace(target_workspace_id, workspace)
    return [
        _member_response(member)
        for member in await _repository(request).list_members(workspace)
    ]


@router.patch(
    "/{target_workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberResponse,
)
async def update_member_role(
    target_workspace_id: UUID,
    user_id: UUID,
    body: UpdateMemberRoleRequest,
    request: Request,
    workspace: OwnedWorkspace,
) -> WorkspaceMemberResponse:
    _require_matching_workspace(target_workspace_id, workspace)
    try:
        member = await _repository(request).update_member_role(
            workspace, user_id, body.role
        )
    except LookupError as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "member_not_found", "message": str(error)},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "protected_membership", "message": str(error)},
        ) from error
    return _member_response(member)


@router.delete(
    "/{target_workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    target_workspace_id: UUID,
    user_id: UUID,
    request: Request,
    workspace: OwnedWorkspace,
) -> None:
    _require_matching_workspace(target_workspace_id, workspace)
    try:
        await _repository(request).remove_member(workspace, user_id)
    except LookupError as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "member_not_found", "message": str(error)},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "protected_membership", "message": str(error)},
        ) from error


@router.get(
    "/{target_workspace_id}/invitations",
    response_model=list[InvitationSummaryResponse],
)
async def list_invitations(
    target_workspace_id: UUID, request: Request, workspace: OwnedWorkspace
) -> list[InvitationSummaryResponse]:
    _require_matching_workspace(target_workspace_id, workspace)
    now = datetime.now(UTC)
    return [
        InvitationSummaryResponse(
            invitation_id=str(invitation.invitation_id),
            email=invitation.email,
            role=cast(Literal["editor", "viewer"], invitation.role),
            status=(
                "accepted"
                if invitation.accepted_at is not None
                else "expired"
                if invitation.expires_at <= now
                else "pending"
            ),
            expires_at=invitation.expires_at,
            accepted_at=invitation.accepted_at,
            created_at=invitation.created_at,
        )
        for invitation in await _repository(request).list_invitations(workspace)
    ]


@router.delete(
    "/{target_workspace_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_invitation(
    target_workspace_id: UUID,
    invitation_id: UUID,
    request: Request,
    workspace: OwnedWorkspace,
) -> None:
    _require_matching_workspace(target_workspace_id, workspace)
    try:
        await _repository(request).revoke_invitation(workspace, invitation_id)
    except LookupError as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "invitation_not_found", "message": str(error)},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "invitation_not_revocable", "message": str(error)},
        ) from error
