"""add ingestion outbox

Revision ID: c14f6d2a9b80
Revises: f9a6c43d120e
Create Date: 2026-09-18 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c14f6d2a9b80"
down_revision: str | None = "f9a6c43d120e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["ingestion_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.execute(
        """
        INSERT INTO ingestion_outbox_events (id, job_id, attempt_count)
        SELECT gen_random_uuid(), id, 0
        FROM ingestion_jobs
        WHERE status = 'queued'
        ON CONFLICT (job_id) DO NOTHING
        """
    )
    op.create_index(
        "ix_ingestion_outbox_unpublished",
        "ingestion_outbox_events",
        ["created_at"],
        postgresql_where=sa.text("published_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ingestion_outbox_unpublished", table_name="ingestion_outbox_events"
    )
    op.drop_table("ingestion_outbox_events")
