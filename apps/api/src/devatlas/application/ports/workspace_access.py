from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from devatlas.application.ports.authentication import AuthenticatedPrincipal

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
