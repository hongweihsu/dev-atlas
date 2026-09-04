"""add document ingestion schema

Revision ID: b5bf51785869
Revises:
Create Date: 2026-09-04 11:00:27.492748
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "b5bf51785869"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(title) > 0", name="ck_documents_title_not_empty"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
    )
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("content_checksum", sa.String(length=64), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "content_checksum ~ '^[0-9a-f]{64}$'",
            name="ck_document_versions_checksum_sha256_hex",
        ),
        sa.CheckConstraint(
            "source_filename <> ''",
            name="ck_document_versions_filename_not_empty",
        ),
        sa.CheckConstraint(
            "byte_size > 0", name="ck_document_versions_byte_size_positive"
        ),
        sa.CheckConstraint(
            "char_length(normalized_text) > 0",
            name="ck_document_versions_text_not_empty",
        ),
        sa.CheckConstraint(
            "character_count > 0",
            name="ck_document_versions_character_count_positive",
        ),
        sa.CheckConstraint(
            "embedding_dimension = 1536",
            name="ck_document_versions_embedding_dimension_v1",
        ),
        sa.CheckConstraint(
            "version_number >= 1",
            name="ck_document_versions_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_versions_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_versions"),
        sa.UniqueConstraint(
            "document_id",
            "content_checksum",
            name="uq_document_versions_document_checksum",
        ),
        sa.UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_versions_document_number",
        ),
    )
    op.create_index(
        "uq_document_versions_one_active",
        "document_versions",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(dim=1536), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("char_length(text) > 0", name="ck_chunks_text_not_empty"),
        sa.CheckConstraint(
            "end_offset - start_offset <= 1000",
            name="ck_chunks_length_within_v1_limit",
        ),
        sa.CheckConstraint(
            "end_offset > start_offset", name="ck_chunks_offset_range_valid"
        ),
        sa.CheckConstraint("ordinal >= 0", name="ck_chunks_ordinal_non_negative"),
        sa.CheckConstraint(
            "start_offset >= 0", name="ck_chunks_start_offset_non_negative"
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.id"],
            name="fk_chunks_document_version_id_document_versions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chunks"),
        sa.UniqueConstraint(
            "document_version_id",
            "ordinal",
            name="uq_chunks_document_version_ordinal",
        ),
    )


def downgrade() -> None:
    op.drop_table("chunks")
    op.drop_index(
        "uq_document_versions_one_active",
        table_name="document_versions",
        postgresql_where=sa.text("is_active = true"),
    )
    op.drop_table("document_versions")
    op.drop_table("documents")
