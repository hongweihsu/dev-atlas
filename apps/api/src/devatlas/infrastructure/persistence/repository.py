from sqlalchemy.ext.asyncio import AsyncSession

from devatlas.application.ports.persistence import NewDocumentRecord
from devatlas.infrastructure.models import Chunk, Document, DocumentVersion


class SqlAlchemyDocumentIngestionRepository:
    """Map an ingestion record to one SQLAlchemy document aggregate."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: NewDocumentRecord) -> None:
        version_record = record.version
        version = DocumentVersion(
            id=version_record.id,
            version_number=version_record.version_number,
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
        document = Document(
            id=record.id,
            title=record.title,
            versions=[version],
        )
        self._session.add(document)
