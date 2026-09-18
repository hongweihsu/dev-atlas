"""add PDF page provenance

Revision ID: e62d7a4c9031
Revises: a82f1c7e4d20
Create Date: 2026-09-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e62d7a4c9031"
down_revision: str | None = "a82f1c7e4d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("page_start", sa.Integer(), nullable=True))
    op.add_column("chunks", sa.Column("page_end", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_chunks_page_start_positive",
        "chunks",
        "page_start IS NULL OR page_start > 0",
    )
    op.create_check_constraint(
        "ck_chunks_page_range_valid",
        "chunks",
        "page_end IS NULL OR page_end >= page_start",
    )


def downgrade() -> None:
    op.drop_constraint("ck_chunks_page_range_valid", "chunks", type_="check")
    op.drop_constraint("ck_chunks_page_start_positive", "chunks", type_="check")
    op.drop_column("chunks", "page_end")
    op.drop_column("chunks", "page_start")
