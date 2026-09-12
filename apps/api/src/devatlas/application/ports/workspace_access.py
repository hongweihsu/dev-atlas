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


class WorkspaceAccessRepository(Protocol):
    async def resolve(
        self,
        principal: AuthenticatedPrincipal,
        workspace_id: UUID,
    ) -> AuthorizedWorkspace | None: ...
