from collections.abc import Sequence

from devatlas.application.ports.retrieval import RetrievalStrategy, RetrievedChunk


class FakeChunkSearchRepository:
    def __init__(self, results: list[RetrievedChunk] | None = None) -> None:
        self.results = results or []
        self.calls: list[
            tuple[str, tuple[float, ...] | None, str, int, RetrievalStrategy]
        ] = []

    async def search(
        self,
        query: str,
        embedding: Sequence[float] | None,
        *,
        model: str,
        limit: int,
        strategy: RetrievalStrategy = "hybrid",
    ) -> list[RetrievedChunk]:
        normalized_embedding = tuple(embedding) if embedding is not None else None
        self.calls.append((query, normalized_embedding, model, limit, strategy))
        return self.results[:limit]
