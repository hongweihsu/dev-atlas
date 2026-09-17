from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from devatlas.application.ports.authentication import AuthenticatedPrincipal
from devatlas.application.ports.workspace_access import (
    AuthorizedWorkspace,
    WorkspaceInvitationResult,
    WorkspaceRole,
)
from devatlas.infrastructure.models import (
    KnowledgeBase,
    User,
    Workspace,
    WorkspaceInvitation,
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
                    email=principal.email,
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
            if principal.email is not None:
                user.email = principal.email

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

    async def list_for_principal(
        self, principal: AuthenticatedPrincipal
    ) -> tuple[AuthorizedWorkspace, ...]:
        statement = (
            select(User.id, Workspace, WorkspaceMembership.role)
            .join(WorkspaceMembership, WorkspaceMembership.user_id == User.id)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .where(
                User.identity_issuer == principal.issuer,
                User.identity_subject == principal.subject,
            )
            .order_by(Workspace.name, Workspace.id)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).all()
        return tuple(
            AuthorizedWorkspace(
                user_id,
                workspace.id,
                workspace.name,
                cast(WorkspaceRole, role),
            )
            for user_id, workspace, role in rows
        )

    async def create_workspace(
        self, principal: AuthenticatedPrincipal, name: str
    ) -> AuthorizedWorkspace:
        async with self._session_factory() as session, session.begin():
            user = await session.scalar(
                select(User).where(
                    User.identity_issuer == principal.issuer,
                    User.identity_subject == principal.subject,
                )
            )
            if user is None:
                raise ValueError("authenticated user has not completed bootstrap")
            workspace = Workspace(name=name)
            session.add(workspace)
            await session.flush()
            session.add_all(
                [
                    WorkspaceMembership(
                        workspace_id=workspace.id, user_id=user.id, role="owner"
                    ),
                    KnowledgeBase(
                        workspace_id=workspace.id, name="General", is_default=True
                    ),
                ]
            )
            return AuthorizedWorkspace(user.id, workspace.id, workspace.name, "owner")

    async def create_invitation(
        self, workspace: AuthorizedWorkspace, email: str, role: WorkspaceRole
    ) -> WorkspaceInvitationResult:
        if role == "owner":
            raise ValueError("invitations may grant editor or viewer access")
        raw_token = token_urlsafe(32)
        invitation = WorkspaceInvitation(
            workspace_id=workspace.workspace_id,
            invited_by_user_id=workspace.user_id,
            email=email.strip().casefold(),
            role=role,
            token_hash=sha256(raw_token.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        async with self._session_factory() as session, session.begin():
            session.add(invitation)
        return WorkspaceInvitationResult(
            invitation.id, raw_token, workspace.workspace_name, invitation.email, role
        )

    async def accept_invitation(
        self, principal: AuthenticatedPrincipal, token: str
    ) -> AuthorizedWorkspace:
        token_hash = sha256(token.encode()).hexdigest()
        async with self._session_factory() as session, session.begin():
            user = await session.scalar(
                select(User).where(
                    User.identity_issuer == principal.issuer,
                    User.identity_subject == principal.subject,
                )
            )
            if user is None or user.email is None:
                raise ValueError("a verified email is required")
            invitation = await session.scalar(
                select(WorkspaceInvitation)
                .where(WorkspaceInvitation.token_hash == token_hash)
                .with_for_update()
            )
            if (
                invitation is None
                or invitation.accepted_at is not None
                or invitation.expires_at <= datetime.now(UTC)
            ):
                raise ValueError("invitation is invalid or expired")
            if invitation.email != user.email.casefold():
                raise PermissionError("invitation belongs to another email")
            await session.execute(
                insert(WorkspaceMembership)
                .values(
                    workspace_id=invitation.workspace_id,
                    user_id=user.id,
                    role=invitation.role,
                )
                .on_conflict_do_nothing()
            )
            invitation.accepted_at = datetime.now(UTC)
            workspace = await session.get(Workspace, invitation.workspace_id)
            if workspace is None:
                raise ValueError("invited workspace no longer exists")
            return AuthorizedWorkspace(
                user.id,
                workspace.id,
                workspace.name,
                cast(WorkspaceRole, invitation.role),
            )
