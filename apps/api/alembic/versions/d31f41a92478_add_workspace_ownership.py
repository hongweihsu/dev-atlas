"""add workspace ownership

Revision ID: d31f41a92478
Revises: c8a2f14d9e31
Create Date: 2026-09-12 00:00:00.000000
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision: str = "d31f41a92478"
down_revision: str | None = "c8a2f14d9e31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
LEGACY_WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000002")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("identity_issuer", sa.String(length=255), nullable=False),
        sa.Column("identity_subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(identity_issuer) > 0",
            name="ck_users_identity_issuer_not_empty",
        ),
        sa.CheckConstraint(
            "char_length(identity_subject) > 0",
            name="ck_users_identity_subject_not_empty",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint(
            "identity_issuer",
            "identity_subject",
            name="uq_users_identity_issuer_subject",
        ),
    )
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(name) > 0", name="ck_workspaces_name_not_empty"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workspaces"),
    )
    op.create_table(
        "workspace_memberships",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'editor', 'viewer')",
            name="ck_workspace_memberships_role_valid",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_workspace_memberships_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_workspace_memberships_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "workspace_id", "user_id", name="pk_workspace_memberships"
        ),
    )

    op.execute(
        sa.text(
            "INSERT INTO users (id, identity_issuer, identity_subject, email, "
            "display_name) VALUES (:id, :issuer, :subject, :email, :name)"
        ).bindparams(
            id=LEGACY_USER_ID,
            issuer="devatlas:legacy",
            subject="personal-owner",
            email=None,
            name="DevAtlas Owner",
        )
    )
    op.execute(
        sa.text("INSERT INTO workspaces (id, name) VALUES (:id, :name)").bindparams(
            id=LEGACY_WORKSPACE_ID, name="Personal Workspace"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO workspace_memberships (workspace_id, user_id, role) "
            "VALUES (:workspace_id, :user_id, 'owner')"
        ).bindparams(
            workspace_id=LEGACY_WORKSPACE_ID,
            user_id=LEGACY_USER_ID,
        )
    )

    op.add_column("documents", sa.Column("workspace_id", sa.Uuid(), nullable=True))
    op.execute(
        sa.text("UPDATE documents SET workspace_id = :workspace_id").bindparams(
            workspace_id=LEGACY_WORKSPACE_ID
        )
    )
    op.alter_column("documents", "workspace_id", nullable=False)
    op.create_foreign_key(
        "fk_documents_workspace_id_workspaces",
        "documents",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_index("ix_documents_active_updated_at", table_name="documents")
    op.create_index(
        "ix_documents_workspace_active_updated_at",
        "documents",
        ["workspace_id", "updated_at"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_documents_workspace_active_updated_at", table_name="documents")
    op.create_index(
        "ix_documents_active_updated_at",
        "documents",
        ["updated_at"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.drop_constraint(
        "fk_documents_workspace_id_workspaces", "documents", type_="foreignkey"
    )
    op.drop_column("documents", "workspace_id")
    op.drop_table("workspace_memberships")
    op.drop_table("workspaces")
    op.drop_table("users")
