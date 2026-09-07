from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    """One retrieved source that an answer is allowed to cite."""

    citation_id: str
    document_id: UUID
    document_title: str
    version_id: UUID
    version_number: int
    chunk_id: UUID
    ordinal: int
    text: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class AnswerGenerationRequest:
    question: str
    context: str
    sources: tuple[EvidenceSource, ...]


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    text: str
    citation_ids: tuple[str, ...]


class AnswerGenerator(Protocol):
    """Generate an answer using only the supplied evidence sources."""

    async def generate(self, request: AnswerGenerationRequest) -> GeneratedAnswer: ...


class AnswerGeneratorUnavailableError(RuntimeError):
    """Raised when an answer provider cannot complete a request."""
