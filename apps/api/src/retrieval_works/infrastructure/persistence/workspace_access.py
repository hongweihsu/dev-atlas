from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from retrieval_works.application.ports.authentication import AuthenticatedPrincipal
from retrieval_works.application.ports.workspace_access import (
    AuthorizedWorkspace,
    WorkspaceInvitationResult,
    WorkspaceInvitationSummary,
    WorkspaceMember,
    WorkspaceRole,
)
from retrieval_works.infrastructure.models import (
    KnowledgeBase,
    User,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
)
from retrieval_works.infrastructure.persistence.unit_of_work import SessionFactory


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
        normalized_email = email.strip().casefold()
        raw_token = token_urlsafe(32)
        invitation = WorkspaceInvitation(
            workspace_id=workspace.workspace_id,
            invited_by_user_id=workspace.user_id,
            email=normalized_email,
            role=role,
            token_hash=sha256(raw_token.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        async with self._session_factory() as session, session.begin():
            existing_member = await session.scalar(
                select(User.id)
                .join(WorkspaceMembership, WorkspaceMembership.user_id == User.id)
                .where(
                    WorkspaceMembership.workspace_id == workspace.workspace_id,
                    func.lower(User.email) == normalized_email,
                )
            )
            if existing_member is not None:
                raise ValueError("email already belongs to a workspace member")
            existing_invitation = await session.scalar(
                select(WorkspaceInvitation.id).where(
                    WorkspaceInvitation.workspace_id == workspace.workspace_id,
                    WorkspaceInvitation.email == normalized_email,
                    WorkspaceInvitation.accepted_at.is_(None),
                    WorkspaceInvitation.expires_at > datetime.now(UTC),
                )
            )
            if existing_invitation is not None:
                raise ValueError("an active invitation already exists for this email")
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

    async def list_members(
        self, workspace: AuthorizedWorkspace
    ) -> tuple[WorkspaceMember, ...]:
        statement = (
            select(User, WorkspaceMembership)
            .join(WorkspaceMembership, WorkspaceMembership.user_id == User.id)
            .where(WorkspaceMembership.workspace_id == workspace.workspace_id)
            .order_by(WorkspaceMembership.created_at, User.id)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).all()
        return tuple(self._member(user, membership) for user, membership in rows)

    async def update_member_role(
        self,
        workspace: AuthorizedWorkspace,
        user_id: UUID,
        role: WorkspaceRole,
    ) -> WorkspaceMember:
        if role == "owner":
            raise ValueError("ownership transfer is not supported")
        async with self._session_factory() as session, session.begin():
            membership = await session.get(
                WorkspaceMembership,
                {"workspace_id": workspace.workspace_id, "user_id": user_id},
                with_for_update=True,
            )
            if membership is None:
                raise LookupError("workspace member was not found")
            if membership.role == "owner":
                raise ValueError("owner membership cannot be changed")
            membership.role = role
            user = await session.get(User, user_id)
            if user is None:  # pragma: no cover - protected by the foreign key
                raise LookupError("workspace member was not found")
            return self._member(user, membership)

    async def remove_member(
        self, workspace: AuthorizedWorkspace, user_id: UUID
    ) -> None:
        async with self._session_factory() as session, session.begin():
            membership = await session.get(
                WorkspaceMembership,
                {"workspace_id": workspace.workspace_id, "user_id": user_id},
                with_for_update=True,
            )
            if membership is None:
                raise LookupError("workspace member was not found")
            if membership.role == "owner":
                raise ValueError("owner membership cannot be removed")
            await session.delete(membership)

    async def transfer_ownership(
        self, workspace: AuthorizedWorkspace, new_owner_user_id: UUID
    ) -> AuthorizedWorkspace:
        if new_owner_user_id == workspace.user_id:
            raise ValueError("the current owner already owns this workspace")
        async with self._session_factory() as session, session.begin():
            memberships = (
                await session.scalars(
                    select(WorkspaceMembership)
                    .where(
                        WorkspaceMembership.workspace_id == workspace.workspace_id,
                        WorkspaceMembership.user_id.in_(
                            (workspace.user_id, new_owner_user_id)
                        ),
                    )
                    .with_for_update()
                )
            ).all()
            by_user_id = {membership.user_id: membership for membership in memberships}
            current_owner = by_user_id.get(workspace.user_id)
            new_owner = by_user_id.get(new_owner_user_id)
            if current_owner is None or current_owner.role != "owner":
                raise ValueError("workspace ownership changed; refresh and try again")
            if new_owner is None:
                raise LookupError("new owner must already be a workspace member")
            if new_owner.role == "owner":
                raise ValueError("the selected member already owns this workspace")
            current_owner.role = "editor"
            new_owner.role = "owner"
            return AuthorizedWorkspace(
                workspace.user_id,
                workspace.workspace_id,
                workspace.workspace_name,
                "editor",
            )

    async def list_invitations(
        self, workspace: AuthorizedWorkspace
    ) -> tuple[WorkspaceInvitationSummary, ...]:
        statement = (
            select(WorkspaceInvitation)
            .where(WorkspaceInvitation.workspace_id == workspace.workspace_id)
            .order_by(WorkspaceInvitation.created_at.desc(), WorkspaceInvitation.id)
        )
        async with self._session_factory() as session:
            invitations = (await session.scalars(statement)).all()
        return tuple(
            WorkspaceInvitationSummary(
                invitation.id,
                invitation.email,
                cast(WorkspaceRole, invitation.role),
                invitation.expires_at,
                invitation.accepted_at,
                invitation.created_at,
            )
            for invitation in invitations
        )

    async def revoke_invitation(
        self, workspace: AuthorizedWorkspace, invitation_id: UUID
    ) -> None:
        async with self._session_factory() as session, session.begin():
            invitation = await session.scalar(
                select(WorkspaceInvitation)
                .where(
                    WorkspaceInvitation.id == invitation_id,
                    WorkspaceInvitation.workspace_id == workspace.workspace_id,
                )
                .with_for_update()
            )
            if invitation is None:
                raise LookupError("workspace invitation was not found")
            if invitation.accepted_at is not None:
                raise ValueError("accepted invitation cannot be revoked")
            await session.execute(
                delete(WorkspaceInvitation).where(
                    WorkspaceInvitation.id == invitation.id
                )
            )

    @staticmethod
    def _member(user: User, membership: WorkspaceMembership) -> WorkspaceMember:
        return WorkspaceMember(
            user.id,
            user.email,
            user.display_name,
            cast(WorkspaceRole, membership.role),
            membership.created_at,
        )
