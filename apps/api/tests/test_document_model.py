from typing import cast

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    String,
    Table,
    UniqueConstraint,
)

from devatlas.infrastructure.models import (
    Chunk,
    Document,
    DocumentVersion,
    KnowledgeBase,
    User,
    Workspace,
    WorkspaceMembership,
)


def test_document_model_exposes_expected_database_contract() -> None:
    table = cast(Table, Document.__table__)

    assert table.name == "documents"
    assert set(table.columns.keys()) == {
        "id",
        "workspace_id",
        "knowledge_base_id",
        "title",
        "created_at",
        "updated_at",
        "archived_at",
    }
    assert list(table.primary_key.columns.keys()) == ["id"]
    assert table.columns.title.nullable is False
    assert cast(String, table.columns.title.type).length == 255

    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert check_names == {"ck_documents_title_not_empty"}
    workspace_key = next(
        key
        for key in table.columns.workspace_id.foreign_keys
        if key.target_fullname == "workspaces.id"
    )
    assert workspace_key.target_fullname == "workspaces.id"
    assert workspace_key.ondelete == "RESTRICT"
    scope_key = next(
        constraint
        for constraint in table.constraints
        if constraint.name == "fk_documents_workspace_knowledge_base"
    )
    assert isinstance(scope_key, ForeignKeyConstraint)


def test_workspace_models_enforce_identity_and_membership_contract() -> None:
    user_table = cast(Table, User.__table__)
    workspace_table = cast(Table, Workspace.__table__)
    membership_table = cast(Table, WorkspaceMembership.__table__)

    assert {constraint.name for constraint in user_table.constraints} >= {
        "uq_users_identity_issuer_subject",
        "ck_users_identity_issuer_not_empty",
        "ck_users_identity_subject_not_empty",
    }
    assert {constraint.name for constraint in workspace_table.constraints} >= {
        "ck_workspaces_name_not_empty"
    }
    assert list(membership_table.primary_key.columns.keys()) == [
        "workspace_id",
        "user_id",
    ]
    role_check = next(
        constraint
        for constraint in membership_table.constraints
        if constraint.name == "ck_workspace_memberships_role_valid"
    )
    assert isinstance(role_check, CheckConstraint)


def test_knowledge_base_model_enforces_workspace_scope_contract() -> None:
    table = cast(Table, KnowledgeBase.__table__)

    assert set(table.columns.keys()) == {
        "id",
        "workspace_id",
        "name",
        "is_default",
        "created_at",
    }
    constraint_names = {constraint.name for constraint in table.constraints}
    assert constraint_names >= {
        "uq_knowledge_bases_workspace_id_id",
        "uq_knowledge_bases_workspace_name",
        "ck_knowledge_bases_name_not_empty",
    }
    default_index = next(
        index
        for index in table.indexes
        if index.name == "uq_knowledge_bases_one_default_per_workspace"
    )
    assert default_index.unique is True


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
