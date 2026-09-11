"""add reversible document archival

Revision ID: c8a2f14d9e31
Revises: b5bf51785869
Create Date: 2026-09-12 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c8a2f14d9e31"
down_revision: str | None = "b5bf51785869"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_documents_active_updated_at",
        "documents",
        ["updated_at"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_documents_active_updated_at", table_name="documents")
    op.drop_column("documents", "archived_at")
