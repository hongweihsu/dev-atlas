from typing import cast

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, String, Table, UniqueConstraint

from devatlas.infrastructure.models import Chunk, Document, DocumentVersion


def test_document_model_exposes_expected_database_contract() -> None:
    table = cast(Table, Document.__table__)

    assert table.name == "documents"
    assert set(table.columns.keys()) == {"id", "title", "created_at", "updated_at"}
    assert list(table.primary_key.columns.keys()) == ["id"]
    assert table.columns.title.nullable is False
    assert cast(String, table.columns.title.type).length == 255

    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert check_names == {"ck_documents_title_not_empty"}


def test_document_version_model_enforces_identity_and_lifecycle_contract() -> None:
    table = cast(Table, DocumentVersion.__table__)

    assert table.name == "document_versions"
    assert set(table.columns.keys()) == {
        "id",
        "document_id",
        "version_number",
        "source_filename",
        "media_type",
        "content_checksum",
        "normalized_text",
        "byte_size",
        "character_count",
        "is_active",
        "embedding_model",
        "embedding_dimension",
        "created_at",
    }

    unique_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert unique_names == {
        "uq_document_versions_document_number",
        "uq_document_versions_document_checksum",
    }

    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert check_names == {
        "ck_document_versions_version_positive",
        "ck_document_versions_filename_not_empty",
        "ck_document_versions_checksum_sha256_hex",
        "ck_document_versions_text_not_empty",
        "ck_document_versions_byte_size_positive",
        "ck_document_versions_character_count_positive",
        "ck_document_versions_embedding_dimension_v1",
    }

    foreign_key = next(iter(table.columns.document_id.foreign_keys))
    assert foreign_key.target_fullname == "documents.id"
    assert foreign_key.ondelete == "CASCADE"

    active_index = next(
        index
        for index in table.indexes
        if index.name == "uq_document_versions_one_active"
    )
    assert active_index.unique is True
    assert active_index.expressions == [table.columns.document_id]
    assert str(active_index.dialect_options["postgresql"]["where"]) == (
        "is_active = true"
    )


def test_chunk_model_enforces_provenance_and_embedding_contract() -> None:
    table = cast(Table, Chunk.__table__)

    assert table.name == "chunks"
    assert set(table.columns.keys()) == {
        "id",
        "document_version_id",
        "ordinal",
        "text",
        "start_offset",
        "end_offset",
        "embedding",
        "created_at",
    }

    unique_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert unique_names == {"uq_chunks_document_version_ordinal"}

    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert check_names == {
        "ck_chunks_ordinal_non_negative",
        "ck_chunks_text_not_empty",
        "ck_chunks_start_offset_non_negative",
        "ck_chunks_offset_range_valid",
        "ck_chunks_length_within_v1_limit",
    }

    foreign_key = next(iter(table.columns.document_version_id.foreign_keys))
    assert foreign_key.target_fullname == "document_versions.id"
    assert foreign_key.ondelete == "CASCADE"

    embedding_type = cast(Vector, table.columns.embedding.type)
    assert embedding_type.dim == 1536
