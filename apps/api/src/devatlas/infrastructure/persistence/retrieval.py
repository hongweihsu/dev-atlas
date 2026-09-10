from collections.abc import Sequence
from typing import Any

import bm25s  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.engine import Result

from devatlas.application.ports.retrieval import RetrievalStrategy, RetrievedChunk
from devatlas.infrastructure.models import Chunk, Document, DocumentVersion
from devatlas.infrastructure.persistence.unit_of_work import SessionFactory


class SqlAlchemyChunkSearchRepository:
    """Search compatible chunks from active document versions with pgvector."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def search(
        self,
        query: str,
        embedding: Sequence[float] | None,
        *,
        model: str,
        limit: int,
        strategy: RetrievalStrategy = "vector",
    ) -> list[RetrievedChunk]:
        del query, strategy
        if embedding is None:
            raise ValueError("vector search requires an embedding")
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
                score=1.0 - float(row.cosine_distance),
                scoring_method="cosine_similarity",
            )
            for row in result
        ]


class SqlAlchemyBm25ChunkSearchRepository:
    """Build a bounded BM25 index over current active chunks for one search."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def search(self, query: str, *, limit: int) -> list[RetrievedChunk]:
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
            )
            .join(DocumentVersion, DocumentVersion.document_id == Document.id)
            .join(Chunk, Chunk.document_version_id == DocumentVersion.id)
            .where(DocumentVersion.is_active.is_(True))
            .order_by(Chunk.id)
        )
        async with self._session_factory() as session:
            rows = list((await session.execute(statement)).all())

        if not rows:
            return []

        corpus_tokens = bm25s.tokenize(
            [row.text for row in rows], stopwords=None, show_progress=False
        )
        retriever = bm25s.BM25(corpus=list(range(len(rows))))
        retriever.index(corpus_tokens, show_progress=False)
        query_tokens = bm25s.tokenize(query, stopwords=None, show_progress=False)
        result = retriever.retrieve(
            query_tokens,
            k=min(limit, len(rows)),
            show_progress=False,
        )

        return [
            RetrievedChunk(
                document_id=rows[int(index)].document_id,
                document_title=rows[int(index)].document_title,
                version_id=rows[int(index)].version_id,
                version_number=rows[int(index)].version_number,
                chunk_id=rows[int(index)].chunk_id,
                ordinal=rows[int(index)].ordinal,
                text=rows[int(index)].text,
                start_offset=rows[int(index)].start_offset,
                end_offset=rows[int(index)].end_offset,
                score=float(score),
                scoring_method="bm25",
            )
            for index, score in zip(result.documents[0], result.scores[0], strict=True)
            if float(score) > 0.0
        ]
