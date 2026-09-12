from sqlalchemy import func, select

from devatlas.application.ports.document_list import DocumentListStatus, DocumentSummary
from devatlas.infrastructure.models import Chunk, Document, DocumentVersion
from devatlas.infrastructure.persistence.unit_of_work import SessionFactory


class SqlAlchemyDocumentListRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def list_documents(
        self, *, status: DocumentListStatus
    ) -> list[DocumentSummary]:
        lifecycle_filter = (
            Document.archived_at.is_(None)
            if status == "active"
            else Document.archived_at.is_not(None)
        )
        statement = (
            select(
                Document.id,
                Document.title,
                DocumentVersion.id.label("active_version_id"),
                DocumentVersion.version_number,
                DocumentVersion.source_filename,
                func.count(Chunk.id).label("chunk_count"),
                Document.updated_at,
                Document.archived_at,
            )
            .join(DocumentVersion, DocumentVersion.document_id == Document.id)
            .join(Chunk, Chunk.document_version_id == DocumentVersion.id)
            .where(
                lifecycle_filter,
                DocumentVersion.is_active.is_(True),
            )
            .group_by(Document.id, DocumentVersion.id)
            .order_by(Document.updated_at.desc(), Document.id)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).all()

        return [
            DocumentSummary(
                document_id=row.id,
                title=row.title,
                active_version_id=row.active_version_id,
                active_version_number=row.version_number,
                source_filename=row.source_filename,
                chunk_count=row.chunk_count,
                updated_at=row.updated_at,
                archived_at=row.archived_at,
            )
            for row in rows
        ]
