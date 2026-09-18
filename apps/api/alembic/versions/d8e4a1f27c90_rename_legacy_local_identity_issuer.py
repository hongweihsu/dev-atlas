"""Rename the legacy local identity issuer after the product rename.

Revision ID: d8e4a1f27c90
Revises: c14f6d2a9b80
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8e4a1f27c90"
down_revision: str | None = "c14f6d2a9b80"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_USER_ID = "00000000-0000-4000-8000-000000000001"


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE users SET identity_issuer = :new_issuer "
            "WHERE id = CAST(:user_id AS UUID) AND identity_issuer = :old_issuer "
            "AND identity_subject = 'personal-owner'"
        ).bindparams(
            user_id=LEGACY_USER_ID,
            old_issuer="devatlas-local",
            new_issuer="retrieval_works-local",
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE users SET identity_issuer = :old_issuer "
            "WHERE id = CAST(:user_id AS UUID) AND identity_issuer = :new_issuer "
            "AND identity_subject = 'personal-owner'"
        ).bindparams(
            user_id=LEGACY_USER_ID,
            old_issuer="devatlas-local",
            new_issuer="retrieval_works-local",
        )
    )
