from typing import cast
from uuid import UUID

from sqlalchemy import select

from devatlas.application.ports.authentication import AuthenticatedPrincipal
from devatlas.application.ports.workspace_access import (
    AuthorizedWorkspace,
    WorkspaceRole,
)
from devatlas.infrastructure.models import User, Workspace, WorkspaceMembership
from devatlas.infrastructure.persistence.unit_of_work import SessionFactory


class SqlAlchemyWorkspaceAccessRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def resolve(
        self,
        principal: AuthenticatedPrincipal,
        workspace_id: UUID,
    ) -> AuthorizedWorkspace | None:
        statement = (
            select(
                User.id.label("user_id"),
                Workspace.id.label("workspace_id"),
                Workspace.name.label("workspace_name"),
                WorkspaceMembership.role,
            )
            .join(
                WorkspaceMembership,
                WorkspaceMembership.user_id == User.id,
            )
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .where(
                User.identity_issuer == principal.issuer,
                User.identity_subject == principal.subject,
                Workspace.id == workspace_id,
            )
        )
        async with self._session_factory() as session:
            row = (await session.execute(statement)).one_or_none()
        if row is None:
            return None
        return AuthorizedWorkspace(
            user_id=row.user_id,
            workspace_id=row.workspace_id,
            workspace_name=row.workspace_name,
            role=cast(WorkspaceRole, row.role),
        )
