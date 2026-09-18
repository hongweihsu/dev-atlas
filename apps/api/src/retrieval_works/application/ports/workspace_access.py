from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from retrieval_works.application.ports.authentication import AuthenticatedPrincipal

WorkspaceRole = Literal["owner", "editor", "viewer"]


@dataclass(frozen=True, slots=True)
class AuthorizedWorkspace:
    user_id: UUID
    workspace_id: UUID
    workspace_name: str
    role: WorkspaceRole


@dataclass(frozen=True, slots=True)
class WorkspaceInvitationResult:
    invitation_id: UUID
    token: str
    workspace_name: str
    email: str
    role: WorkspaceRole


@dataclass(frozen=True, slots=True)
class WorkspaceMember:
    user_id: UUID
    email: str | None
    display_name: str | None
    role: WorkspaceRole
    joined_at: datetime


@dataclass(frozen=True, slots=True)
class WorkspaceInvitationSummary:
    invitation_id: UUID
    email: str
    role: WorkspaceRole
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class WorkspaceAccessRepository(Protocol):
    async def bootstrap_personal_workspace(
        self, principal: AuthenticatedPrincipal
    ) -> AuthorizedWorkspace: ...

    async def resolve(
        self,
        principal: AuthenticatedPrincipal,
        workspace_id: UUID,
    ) -> AuthorizedWorkspace | None: ...

    async def list_for_principal(
        self, principal: AuthenticatedPrincipal
    ) -> tuple[AuthorizedWorkspace, ...]: ...

    async def create_workspace(
        self, principal: AuthenticatedPrincipal, name: str
    ) -> AuthorizedWorkspace: ...

    async def create_invitation(
        self,
        workspace: AuthorizedWorkspace,
        email: str,
        role: WorkspaceRole,
    ) -> WorkspaceInvitationResult: ...

    async def accept_invitation(
        self, principal: AuthenticatedPrincipal, token: str
    ) -> AuthorizedWorkspace: ...

    async def list_members(
        self, workspace: AuthorizedWorkspace
    ) -> tuple[WorkspaceMember, ...]: ...

    async def update_member_role(
        self,
        workspace: AuthorizedWorkspace,
        user_id: UUID,
        role: WorkspaceRole,
    ) -> WorkspaceMember: ...

    async def remove_member(
        self, workspace: AuthorizedWorkspace, user_id: UUID
    ) -> None: ...

    async def list_invitations(
        self, workspace: AuthorizedWorkspace
    ) -> tuple[WorkspaceInvitationSummary, ...]: ...

    async def revoke_invitation(
        self, workspace: AuthorizedWorkspace, invitation_id: UUID
    ) -> None: ...
