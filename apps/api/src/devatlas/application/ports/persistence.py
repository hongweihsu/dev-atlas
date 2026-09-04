from collections.abc import Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID


@dataclass(frozen=True, slots=True)
class NewChunkRecord:
    id: UUID
    ordinal: int
    text: str
    start_offset: int
    end_offset: int
    embedding: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class NewDocumentVersionRecord:
    id: UUID
    version_number: int
    source_filename: str
    media_type: str
    content_checksum: str
    normalized_text: str
    byte_size: int
    character_count: int
    is_active: bool
    embedding_model: str
    embedding_dimension: int
    chunks: tuple[NewChunkRecord, ...]


@dataclass(frozen=True, slots=True)
class NewDocumentRecord:
    id: UUID
    title: str
    version: NewDocumentVersionRecord


class DocumentIngestionRepository(Protocol):
    """Persistence operations required by new-document ingestion."""

    async def add(self, document: NewDocumentRecord) -> None:
        """Stage a complete document aggregate in the current transaction."""
        ...


class IngestionUnitOfWork(Protocol):
    """Own one atomic persistence transaction for document ingestion."""

    @property
    def documents(self) -> DocumentIngestionRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class IngestionUnitOfWorkFactory(Protocol):
    def __call__(self) -> IngestionUnitOfWork: ...


def chunk_embeddings(
    embeddings: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], ...]:
    """Freeze provider output before it crosses the persistence boundary."""
    return tuple(tuple(vector) for vector in embeddings)
