from uuid import UUID

from sqlalchemy import func, select, update

from retrieval_works.application.ports.document_versions import (
    DocumentVersionNotFoundError,
    DocumentVersionSummary,
)
from retrieval_works.application.ports.persistence import (
    DocumentArchivedError,
    DocumentNotFoundError,
)
from retrieval_works.infrastructure.models import Chunk, Document, DocumentVersion
from retrieval_works.infrastructure.persistence.unit_of_work import SessionFactory


class SqlAlchemyDocumentVersionRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def list_versions(
        self, workspace_id: UUID, document_id: UUID
    ) -> list[DocumentVersionSummary]:
        async with self._session_factory() as session:
            exists = await session.scalar(
                select(Document.id).where(
                    Document.id == document_id,
                    Document.workspace_id == workspace_id,
                )
            )
            if exists is None:
                raise DocumentNotFoundError(f"document {document_id} was not found")
            rows = (
                await session.execute(
                    select(
                        DocumentVersion.id,
                        DocumentVersion.version_number,
                        DocumentVersion.source_filename,
                        DocumentVersion.media_type,
                        DocumentVersion.content_checksum,
                        DocumentVersion.character_count,
                        func.count(Chunk.id).label("chunk_count"),
                        DocumentVersion.embedding_model,
                        DocumentVersion.embedding_dimension,
                        DocumentVersion.is_active,
                        DocumentVersion.created_at,
                    )
                    .outerjoin(Chunk, Chunk.document_version_id == DocumentVersion.id)
                    .where(DocumentVersion.document_id == document_id)
                    .group_by(DocumentVersion.id)
                    .order_by(DocumentVersion.version_number.desc())
                )
            ).all()
        return [
            DocumentVersionSummary(
                version_id=row.id,
                version_number=row.version_number,
                source_filename=row.source_filename,
                media_type=row.media_type,
                content_checksum=row.content_checksum,
                character_count=row.character_count,
                chunk_count=row.chunk_count,
                embedding_model=row.embedding_model,
                embedding_dimension=row.embedding_dimension,
                is_active=row.is_active,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def activate_version(
        self, workspace_id: UUID, document_id: UUID, version_id: UUID
    ) -> None:
        async with self._session_factory() as session, session.begin():
            document = await session.scalar(
                select(Document)
                .where(
                    Document.id == document_id,
                    Document.workspace_id == workspace_id,
                )
                .with_for_update()
            )
            if document is None:
                raise DocumentNotFoundError(f"document {document_id} was not found")
            if document.archived_at is not None:
                raise DocumentArchivedError(
                    f"document {document_id} must be restored before activating "
                    "a version"
                )
            target = await session.scalar(
                select(DocumentVersion.id).where(
                    DocumentVersion.id == version_id,
                    DocumentVersion.document_id == document_id,
                )
            )
            if target is None:
                raise DocumentVersionNotFoundError(
                    f"version {version_id} was not found for document {document_id}"
                )
            await session.execute(
                update(DocumentVersion)
                .where(DocumentVersion.document_id == document_id)
                .values(is_active=False)
            )
            await session.execute(
                update(DocumentVersion)
                .where(DocumentVersion.id == version_id)
                .values(is_active=True)
            )
            await session.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(updated_at=func.now())
            )
