from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Result

from devatlas.application.ports.retrieval import RetrievedChunk
from devatlas.infrastructure.models import Chunk, Document, DocumentVersion
from devatlas.infrastructure.persistence.unit_of_work import SessionFactory


class SqlAlchemyChunkSearchRepository:
    """Search compatible chunks from active document versions with pgvector."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def search(
        self,
        embedding: Sequence[float],
        *,
        model: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        distance = Chunk.embedding.cosine_distance(list(embedding)).label(
            "cosine_distance"
        )
        statement = (
            select(
                Document.id.label("document_id"),
                Document.title.label("document_title"),
                DocumentVersion.id.label("version_id"),
                DocumentVersion.version_number,
                Chunk.id.label("chunk_id"),
                Chunk.ordinal,
                Chunk.text,
                Chunk.start_offset,
                Chunk.end_offset,
                distance,
            )
            .join(DocumentVersion, DocumentVersion.document_id == Document.id)
            .join(Chunk, Chunk.document_version_id == DocumentVersion.id)
            .where(
                DocumentVersion.is_active.is_(True),
                DocumentVersion.embedding_model == model,
                DocumentVersion.embedding_dimension == len(embedding),
            )
            .order_by(distance, Chunk.id)
            .limit(limit)
        )

        async with self._session_factory() as session:
            return self._rows_to_chunks(await session.execute(statement))

    @staticmethod
    def _rows_to_chunks(result: Result[Any]) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                document_id=row.document_id,
                document_title=row.document_title,
                version_id=row.version_id,
                version_number=row.version_number,
                chunk_id=row.chunk_id,
                ordinal=row.ordinal,
                text=row.text,
                start_offset=row.start_offset,
                end_offset=row.end_offset,
                similarity=1.0 - float(row.cosine_distance),
            )
            for row in result
        ]
