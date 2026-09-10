from collections.abc import Sequence
from uuid import UUID

import pytest

from devatlas.application.hybrid_retrieval import (
    HybridChunkSearchRepository,
    reciprocal_rank_fusion,
)
from devatlas.application.ports.retrieval import RetrievalStrategy, RetrievedChunk


def make_chunk(number: int) -> RetrievedChunk:
    return RetrievedChunk(
        document_id=UUID(int=100 + number),
        document_title=f"Document {number}",
        version_id=UUID(int=200 + number),
        version_number=1,
        chunk_id=UUID(int=number),
        ordinal=0,
        text=f"chunk {number}",
        start_offset=0,
        end_offset=7,
        score=0.5,
        scoring_method="cosine_similarity",
    )


def test_rrf_rewards_chunks_found_by_both_retrievers() -> None:
    first, shared, third = make_chunk(1), make_chunk(2), make_chunk(3)

    results = reciprocal_rank_fusion(
        [first, shared],
        [third, shared],
        limit=3,
    )

    assert [result.chunk_id for result in results] == [
        shared.chunk_id,
        first.chunk_id,
        third.chunk_id,
    ]
    assert results[0].score == pytest.approx(2 / 62)
    assert results[0].scoring_method == "rrf"


def test_rrf_breaks_equal_rank_ties_by_stable_chunk_id() -> None:
    lower_id, higher_id = make_chunk(1), make_chunk(2)

    results = reciprocal_rank_fusion(
        [higher_id],
        [lower_id],
        limit=2,
    )

    assert [result.chunk_id for result in results] == [
        lower_id.chunk_id,
        higher_id.chunk_id,
    ]


class VectorStub:
    def __init__(self, results: list[RetrievedChunk]) -> None:
        self.results = results
        self.calls: list[tuple[str, tuple[float, ...], str, int]] = []

    async def search(
        self,
        query: str,
        embedding: Sequence[float] | None,
        *,
        model: str,
        limit: int,
        strategy: RetrievalStrategy = "hybrid",
    ) -> list[RetrievedChunk]:
        assert embedding is not None
        self.calls.append((query, tuple(embedding), model, limit))
        return self.results[:limit]


class LexicalStub:
    def __init__(self, results: list[RetrievedChunk]) -> None:
        self.results = results
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, *, limit: int) -> list[RetrievedChunk]:
        self.calls.append((query, limit))
        return self.results[:limit]


@pytest.mark.asyncio
async def test_hybrid_repository_collects_bounded_candidates_from_both() -> None:
    shared = make_chunk(1)
    vector = VectorStub([shared])
    lexical = LexicalStub([shared])
    repository = HybridChunkSearchRepository(vector=vector, lexical=lexical)

    results = await repository.search(
        "DVX-4827",
        [0.1, 0.2],
        model="embedding-v1",
        limit=3,
    )

    assert results[0].chunk_id == shared.chunk_id
    assert vector.calls == [("DVX-4827", (0.1, 0.2), "embedding-v1", 12)]
    assert lexical.calls == [("DVX-4827", 12)]
