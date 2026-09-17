from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from devatlas.infrastructure.models.base import Base

if TYPE_CHECKING:
    from devatlas.infrastructure.models.document import Document


class User(Base):
    """Local identity linked to a stable subject from an authentication issuer."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint(
            "identity_issuer",
            "identity_subject",
            name="uq_users_identity_issuer_subject",
        ),
        CheckConstraint(
            "char_length(identity_issuer) > 0",
            name="ck_users_identity_issuer_not_empty",
        ),
        CheckConstraint(
            "char_length(identity_subject) > 0",
            name="ck_users_identity_subject_not_empty",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    identity_issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    identity_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Workspace(Base):
    """Tenant boundary that owns documents and memberships."""

    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint("char_length(name) > 0", name="ck_workspaces_name_not_empty"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan", passive_deletes=True
    )
    documents: Mapped[list["Document"]] = relationship(back_populates="workspace")
    knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship(
        back_populates="workspace"
    )


class KnowledgeBase(Base):
    """A selectable retrieval scope owned by exactly one workspace."""

    __tablename__ = "knowledge_bases"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "id",
            name="uq_knowledge_bases_workspace_id_id",
        ),
        UniqueConstraint(
            "workspace_id",
            "name",
            name="uq_knowledge_bases_workspace_name",
        ),
        CheckConstraint(
            "char_length(name) > 0",
            name="ck_knowledge_bases_name_not_empty",
        ),
        Index(
            "uq_knowledge_bases_one_default_per_workspace",
            "workspace_id",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workspaces.id",
            name="fk_knowledge_bases_workspace_id_workspaces",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    workspace: Mapped[Workspace] = relationship(back_populates="knowledge_bases")


class WorkspaceMembership(Base):
    """A user's role inside one workspace."""

    __tablename__ = "workspace_memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'editor', 'viewer')",
            name="ck_workspace_memberships_role_valid",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workspaces.id",
            name="fk_workspace_memberships_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "users.id",
            name="fk_workspace_memberships_user_id_users",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    workspace: Mapped[Workspace] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class WorkspaceInvitation(Base):
    """Single-use, expiring invitation bound to a verified email address."""

    __tablename__ = "workspace_invitations"
    __table_args__ = (
        CheckConstraint(
            "role IN ('editor', 'viewer')",
            name="ck_workspace_invitations_role_valid",
        ),
        UniqueConstraint("token_hash", name="uq_workspace_invitations_token_hash"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    invited_by_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
