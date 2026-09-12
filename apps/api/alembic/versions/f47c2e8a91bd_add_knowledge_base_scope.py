"""add knowledge base search scope

Revision ID: f47c2e8a91bd
Revises: d31f41a92478
Create Date: 2026-09-13 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f47c2e8a91bd"
down_revision: str | None = "d31f41a92478"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(name) > 0",
            name="ck_knowledge_bases_name_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_knowledge_bases_workspace_id_workspaces",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_bases"),
        sa.UniqueConstraint(
            "workspace_id",
            "id",
            name="uq_knowledge_bases_workspace_id_id",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "name",
            name="uq_knowledge_bases_workspace_name",
        ),
    )
    op.create_index(
        "uq_knowledge_bases_one_default_per_workspace",
        "knowledge_bases",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )
    op.execute(
        "INSERT INTO knowledge_bases (id, workspace_id, name, is_default) "
        "SELECT gen_random_uuid(), id, 'General', true FROM workspaces"
    )

    op.add_column(
        "documents",
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        "UPDATE documents AS document SET knowledge_base_id = knowledge_base.id "
        "FROM knowledge_bases AS knowledge_base "
        "WHERE knowledge_base.workspace_id = document.workspace_id "
        "AND knowledge_base.is_default = true"
    )
    op.alter_column("documents", "knowledge_base_id", nullable=False)
    op.create_foreign_key(
        "fk_documents_workspace_knowledge_base",
        "documents",
        "knowledge_bases",
        ["workspace_id", "knowledge_base_id"],
        ["workspace_id", "id"],
        ondelete="RESTRICT",
    )
    op.drop_index("ix_documents_workspace_active_updated_at", table_name="documents")
    op.create_index(
        "ix_documents_workspace_knowledge_base_active_updated_at",
        "documents",
        ["workspace_id", "knowledge_base_id", "updated_at"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_documents_workspace_knowledge_base_active_updated_at",
        table_name="documents",
    )
    op.create_index(
        "ix_documents_workspace_active_updated_at",
        "documents",
        ["workspace_id", "updated_at"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.drop_constraint(
        "fk_documents_workspace_knowledge_base",
        "documents",
        type_="foreignkey",
    )
    op.drop_column("documents", "knowledge_base_id")
    op.drop_index(
        "uq_knowledge_bases_one_default_per_workspace",
        table_name="knowledge_bases",
    )
    op.drop_table("knowledge_bases")
