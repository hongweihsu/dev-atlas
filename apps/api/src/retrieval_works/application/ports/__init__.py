"""Interfaces implemented by external infrastructure adapters."""

from retrieval_works.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProvider,
    validate_embedding_batch,
)
from retrieval_works.application.ports.generation import (
    AnswerGenerationRequest,
    AnswerGenerator,
    AnswerGeneratorUnavailableError,
    EvidenceSource,
    GeneratedAnswer,
    InvalidGeneratedAnswerError,
)
from retrieval_works.application.ports.persistence import (
    DocumentIngestionRepository,
    IngestionUnitOfWork,
    IngestionUnitOfWorkFactory,
    NewChunkRecord,
    NewDocumentRecord,
    NewDocumentVersionRecord,
)

__all__ = [
    "EmbeddingBatchError",
    "EmbeddingProvider",
    "AnswerGenerationRequest",
    "AnswerGenerator",
    "AnswerGeneratorUnavailableError",
    "EvidenceSource",
    "GeneratedAnswer",
    "InvalidGeneratedAnswerError",
    "DocumentIngestionRepository",
    "IngestionUnitOfWork",
    "IngestionUnitOfWorkFactory",
    "NewChunkRecord",
    "NewDocumentRecord",
    "NewDocumentVersionRecord",
    "validate_embedding_batch",
]
