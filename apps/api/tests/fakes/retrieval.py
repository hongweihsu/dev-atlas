from collections.abc import Sequence
from uuid import UUID

from devatlas.application.ports.retrieval import RetrievalStrategy, RetrievedChunk


class FakeChunkSearchRepository:
    def __init__(self, results: list[RetrievedChunk] | None = None) -> None:
        self.results = results or []
        self.calls: list[
            tuple[UUID, str, tuple[float, ...] | None, str, int, RetrievalStrategy]
        ] = []

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
        del knowledge_base_ids
        normalized_embedding = tuple(embedding) if embedding is not None else None
        self.calls.append(
            (workspace_id, query, normalized_embedding, model, limit, strategy)
        )
        return self.results[:limit]
