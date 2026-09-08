"""Interfaces implemented by external infrastructure adapters."""

from devatlas.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProvider,
    validate_embedding_batch,
)
from devatlas.application.ports.generation import (
    AnswerGenerationRequest,
    AnswerGenerator,
    AnswerGeneratorUnavailableError,
    EvidenceSource,
    GeneratedAnswer,
    InvalidGeneratedAnswerError,
)
from devatlas.application.ports.persistence import (
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
