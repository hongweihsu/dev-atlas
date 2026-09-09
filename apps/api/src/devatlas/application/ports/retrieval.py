from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


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
    similarity: float


class ChunkSearchRepository(Protocol):
    async def search(
        self,
        query: str,
        embedding: Sequence[float],
        *,
        model: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        """Return compatible active-version chunks ordered by relevance."""
        ...


class LexicalChunkSearchRepository(Protocol):
    async def search(self, query: str, *, limit: int) -> list[RetrievedChunk]:
        """Return active-version chunks ordered by lexical relevance."""
        ...
