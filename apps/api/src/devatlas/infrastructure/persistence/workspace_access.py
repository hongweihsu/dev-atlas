from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from devatlas.application.ports.authentication import AuthenticatedPrincipal
from devatlas.application.ports.workspace_access import (
    AuthorizedWorkspace,
    WorkspaceRole,
)
from devatlas.infrastructure.models import (
    KnowledgeBase,
    User,
    Workspace,
    WorkspaceMembership,
)
from devatlas.infrastructure.persistence.unit_of_work import SessionFactory


class SqlAlchemyWorkspaceAccessRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def bootstrap_personal_workspace(
        self, principal: AuthenticatedPrincipal
    ) -> AuthorizedWorkspace:
        """Idempotently create the authenticated user's first personal workspace."""
        async with self._session_factory() as session, session.begin():
            await session.execute(
                insert(User)
                .values(
                    identity_issuer=principal.issuer,
                    identity_subject=principal.subject,
                )
                .on_conflict_do_nothing(
                    index_elements=[User.identity_issuer, User.identity_subject]
                )
            )
            user = await session.scalar(
                select(User)
                .where(
                    User.identity_issuer == principal.issuer,
                    User.identity_subject == principal.subject,
                )
                .with_for_update()
            )
            if user is None:  # pragma: no cover - guarded by the insert above
                raise RuntimeError("authenticated user could not be persisted")

            existing = (
                await session.execute(
                    select(Workspace, WorkspaceMembership.role)
                    .join(
                        WorkspaceMembership,
                        WorkspaceMembership.workspace_id == Workspace.id,
                    )
                    .where(WorkspaceMembership.user_id == user.id)
                    .order_by(WorkspaceMembership.created_at, Workspace.id)
                    .limit(1)
                )
            ).one_or_none()
            if existing is not None:
                workspace, role = existing
                return AuthorizedWorkspace(
                    user_id=user.id,
                    workspace_id=workspace.id,
                    workspace_name=workspace.name,
                    role=cast(WorkspaceRole, role),
                )

            workspace = Workspace(name="Personal Workspace")
            session.add(workspace)
            await session.flush()
            session.add_all(
                [
                    WorkspaceMembership(
                        workspace_id=workspace.id,
                        user_id=user.id,
                        role="owner",
                    ),
                    KnowledgeBase(
                        workspace_id=workspace.id,
                        name="General",
                        is_default=True,
                    ),
                ]
            )
            return AuthorizedWorkspace(
                user_id=user.id,
                workspace_id=workspace.id,
                workspace_name=workspace.name,
                role="owner",
            )

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
