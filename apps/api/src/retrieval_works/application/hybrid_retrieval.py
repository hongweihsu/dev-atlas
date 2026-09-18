import asyncio
from collections.abc import Sequence
from dataclasses import replace
from uuid import UUID

from retrieval_works.application.ports.retrieval import (
    ChunkSearchRepository,
    LexicalChunkSearchRepository,
    RetrievalStrategy,
    RetrievedChunk,
)

RRF_RANK_CONSTANT = 60
MAX_CANDIDATE_LIMIT = 20


class HybridChunkSearchRepository:
    """Fuse semantic and lexical chunk ranks with deterministic RRF."""

    def __init__(
        self,
        *,
        vector: ChunkSearchRepository,
        lexical: LexicalChunkSearchRepository,
    ) -> None:
        self._vector = vector
        self._lexical = lexical

    async def search(
        self,
        query: str,
        embedding: Sequence[float] | None,
        *,
        workspace_id: UUID,
        model: str,
        limit: int,
        strategy: RetrievalStrategy = "hybrid",
        knowledge_base_ids: tuple[UUID, ...] = (),
    ) -> list[RetrievedChunk]:
        candidate_limit = min(MAX_CANDIDATE_LIMIT, max(limit * 4, limit))
        if strategy == "lexical":
            if not knowledge_base_ids:
                return (
                    await self._lexical.search(
                        query, workspace_id=workspace_id, limit=candidate_limit
                    )
                )[:limit]
            return (
                await self._lexical.search(
                    query,
                    workspace_id=workspace_id,
                    limit=candidate_limit,
                    knowledge_base_ids=knowledge_base_ids,
                )
            )[:limit]
        if embedding is None:
            raise ValueError("vector and hybrid search require an embedding")
        if strategy == "vector":
            if not knowledge_base_ids:
                return (
                    await self._vector.search(
                        query,
                        embedding,
                        workspace_id=workspace_id,
                        model=model,
                        limit=candidate_limit,
                        strategy="vector",
                    )
                )[:limit]
            return (
                await self._vector.search(
                    query,
                    embedding,
                    workspace_id=workspace_id,
                    model=model,
                    limit=candidate_limit,
                    strategy="vector",
                    knowledge_base_ids=knowledge_base_ids,
                )
            )[:limit]
        if not knowledge_base_ids:
            vector_results, lexical_results = await asyncio.gather(
                self._vector.search(
                    query,
                    embedding,
                    workspace_id=workspace_id,
                    model=model,
                    limit=candidate_limit,
                    strategy="vector",
                ),
                self._lexical.search(
                    query, workspace_id=workspace_id, limit=candidate_limit
                ),
            )
        else:
            vector_results, lexical_results = await asyncio.gather(
                self._vector.search(
                    query,
                    embedding,
                    workspace_id=workspace_id,
                    model=model,
                    limit=candidate_limit,
                    strategy="vector",
                    knowledge_base_ids=knowledge_base_ids,
                ),
                self._lexical.search(
                    query,
                    workspace_id=workspace_id,
                    limit=candidate_limit,
                    knowledge_base_ids=knowledge_base_ids,
                ),
            )
        return reciprocal_rank_fusion(
            vector_results,
            lexical_results,
            limit=limit,
        )


def reciprocal_rank_fusion(
    *rankings: Sequence[RetrievedChunk],
    limit: int,
    rank_constant: int = RRF_RANK_CONSTANT,
) -> list[RetrievedChunk]:
    scores: dict[UUID, float] = {}
    chunks: dict[UUID, RetrievedChunk] = {}
    best_rank: dict[UUID, int] = {}

    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            chunks[chunk.chunk_id] = chunk
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (
                rank_constant + rank
            )
            best_rank[chunk.chunk_id] = min(best_rank.get(chunk.chunk_id, rank), rank)

    ordered_ids = sorted(
        scores,
        key=lambda chunk_id: (
            -scores[chunk_id],
            best_rank[chunk_id],
            str(chunk_id),
        ),
    )
    return [
        replace(
            chunks[chunk_id],
            score=scores[chunk_id],
            scoring_method="rrf",
        )
        for chunk_id in ordered_ids[:limit]
    ]
