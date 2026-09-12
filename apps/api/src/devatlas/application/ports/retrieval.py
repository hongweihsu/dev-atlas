from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

type RetrievalStrategy = Literal["vector", "lexical", "hybrid"]
type ScoringMethod = Literal["cosine_similarity", "bm25", "rrf"]


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    document_id: UUID
    document_title: str
    version_id: UUID
    version_number: int
    chunk_id: UUID
    ordinal: int
    text: str
    start_offset: int
    end_offset: int
    score: float
    scoring_method: ScoringMethod


class ChunkSearchRepository(Protocol):
    async def search(
        self,
        query: str,
        embedding: Sequence[float] | None,
        *,
        workspace_id: UUID,
        model: str,
        limit: int,
        strategy: RetrievalStrategy = "hybrid",
    ) -> list[RetrievedChunk]:
        """Return compatible active-version chunks ordered by relevance."""
        ...


class LexicalChunkSearchRepository(Protocol):
    async def search(
        self, query: str, *, workspace_id: UUID, limit: int
    ) -> list[RetrievedChunk]:
        """Return active-version chunks ordered by lexical relevance."""
        ...
