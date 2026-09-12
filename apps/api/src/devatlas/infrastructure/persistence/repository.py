from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from devatlas.application.ports.persistence import (
    DocumentArchivedError,
    DocumentNotFoundError,
    DuplicateDocumentContentError,
    NewDocumentRecord,
    NewDocumentVersionRecord,
)
from devatlas.infrastructure.models import Chunk, Document, DocumentVersion


class SqlAlchemyDocumentIngestionRepository:
    """Map an ingestion record to one SQLAlchemy document aggregate."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: NewDocumentRecord) -> None:
        await self._session.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtext(record.version.content_checksum)
                )
            )
        )
        duplicate = (
            await self._session.execute(
                select(DocumentVersion.document_id, Document.archived_at)
                .join(Document, Document.id == DocumentVersion.document_id)
                .where(
                    DocumentVersion.content_checksum
                    == record.version.content_checksum
                )
            )
        ).first()
        if duplicate is not None:
            raise DuplicateDocumentContentError(
                "this content already exists in another document",
                document_id=duplicate.document_id,
                document_archived=duplicate.archived_at is not None,
            )
        version = self._map_version(record.version)
        document = Document(
            id=record.id,
            title=record.title,
            versions=[version],
        )
        self._session.add(document)

    async def add_version(
        self,
        document_id: UUID,
        version: NewDocumentVersionRecord,
    ) -> int:
        document = await self._session.scalar(
            select(Document).where(Document.id == document_id).with_for_update()
        )
        if document is None:
            raise DocumentNotFoundError(f"document {document_id} was not found")
        if document.archived_at is not None:
            raise DocumentArchivedError(
                f"document {document_id} must be restored before adding a version"
            )

        duplicate_id = await self._session.scalar(
            select(DocumentVersion.id).where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.content_checksum == version.content_checksum,
            )
        )
        if duplicate_id is not None:
            raise DuplicateDocumentContentError(
                "this document already has a version with the same content"
            )

        latest_number = await self._session.scalar(
            select(func.max(DocumentVersion.version_number)).where(
                DocumentVersion.document_id == document_id
            )
        )
        next_number = (latest_number or 0) + 1
        await self._session.execute(
            update(DocumentVersion)
            .where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.is_active.is_(True),
            )
            .values(is_active=False)
        )
        self._session.add(
            self._map_version(
                version,
                document_id=document_id,
                version_number=next_number,
            )
        )
        return next_number

    async def ensure_version_target(self, document_id: UUID) -> None:
        document = await self._session.scalar(
            select(Document).where(Document.id == document_id)
        )
        if document is None:
            raise DocumentNotFoundError(f"document {document_id} was not found")
        if document.archived_at is not None:
            raise DocumentArchivedError(
                f"document {document_id} must be restored before adding a version"
            )

    @staticmethod
    def _map_version(
        version_record: NewDocumentVersionRecord,
        *,
        document_id: UUID | None = None,
        version_number: int | None = None,
    ) -> DocumentVersion:
        mapped = DocumentVersion(
            id=version_record.id,
            version_number=(
                version_record.version_number
                if version_number is None
                else version_number
            ),
            source_filename=version_record.source_filename,
            media_type=version_record.media_type,
            content_checksum=version_record.content_checksum,
            normalized_text=version_record.normalized_text,
            byte_size=version_record.byte_size,
            character_count=version_record.character_count,
            is_active=version_record.is_active,
            embedding_model=version_record.embedding_model,
            embedding_dimension=version_record.embedding_dimension,
            chunks=[
                Chunk(
                    id=chunk.id,
                    ordinal=chunk.ordinal,
                    text=chunk.text,
                    start_offset=chunk.start_offset,
                    end_offset=chunk.end_offset,
                    embedding=list(chunk.embedding),
                )
                for chunk in version_record.chunks
            ],
        )
        if document_id is not None:
            mapped.document_id = document_id
        return mapped
