from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from devatlas.infrastructure.models.base import Base

if TYPE_CHECKING:
    from devatlas.infrastructure.models.identity import Workspace


class Document(Base):
    """Stable identity for a logical document across content versions."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "char_length(title) > 0",
            name="ck_documents_title_not_empty",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workspaces.id",
            name="fk_documents_workspace_id_workspaces",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    workspace: Mapped["Workspace"] = relationship(back_populates="documents")


class DocumentVersion(Base):
    """Immutable normalized content and embedding configuration for a document."""

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_versions_document_number",
        ),
        UniqueConstraint(
            "document_id",
            "content_checksum",
            name="uq_document_versions_document_checksum",
        ),
        CheckConstraint(
            "version_number >= 1",
            name="ck_document_versions_version_positive",
        ),
        CheckConstraint(
            "source_filename <> ''",
            name="ck_document_versions_filename_not_empty",
        ),
        CheckConstraint(
            "content_checksum ~ '^[0-9a-f]{64}$'",
            name="ck_document_versions_checksum_sha256_hex",
        ),
        CheckConstraint(
            "char_length(normalized_text) > 0",
            name="ck_document_versions_text_not_empty",
        ),
        CheckConstraint(
            "byte_size > 0",
            name="ck_document_versions_byte_size_positive",
        ),
        CheckConstraint(
            "character_count > 0",
            name="ck_document_versions_character_count_positive",
        ),
        CheckConstraint(
            "embedding_dimension = 1536",
            name="ck_document_versions_embedding_dimension_v1",
        ),
        Index(
            "uq_document_versions_one_active",
            "document_id",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "documents.id",
            name="fk_document_versions_document_id_documents",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    document: Mapped[Document] = relationship(back_populates="versions")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document_version",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Chunk(Base):
    """Traceable, embedded text segment belonging to one document version."""

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id",
            "ordinal",
            name="uq_chunks_document_version_ordinal",
        ),
        CheckConstraint(
            "ordinal >= 0",
            name="ck_chunks_ordinal_non_negative",
        ),
        CheckConstraint(
            "char_length(text) > 0",
            name="ck_chunks_text_not_empty",
        ),
        CheckConstraint(
            "start_offset >= 0",
            name="ck_chunks_start_offset_non_negative",
        ),
        CheckConstraint(
            "end_offset > start_offset",
            name="ck_chunks_offset_range_valid",
        ),
        CheckConstraint(
            "end_offset - start_offset <= 1000",
            name="ck_chunks_length_within_v1_limit",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    document_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "document_versions.id",
            name="fk_chunks_document_version_id_document_versions",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    document_version: Mapped[DocumentVersion] = relationship(back_populates="chunks")
