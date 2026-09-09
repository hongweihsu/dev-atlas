from collections.abc import Sequence

from devatlas.application.ports.retrieval import RetrievedChunk


class FakeChunkSearchRepository:
    def __init__(self, results: list[RetrievedChunk] | None = None) -> None:
        self.results = results or []
        self.calls: list[tuple[str, tuple[float, ...], str, int]] = []

    async def search(
        self,
        query: str,
        embedding: Sequence[float],
        *,
        model: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        self.calls.append((query, tuple(embedding), model, limit))
        return self.results[:limit]
