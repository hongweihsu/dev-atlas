"""Deterministic test doubles for external dependencies."""

from tests.fakes.embedding import DeterministicEmbeddingProvider
from tests.fakes.persistence import FakeIngestionUnitOfWorkFactory
from tests.fakes.retrieval import FakeChunkSearchRepository

__all__ = [
    "DeterministicEmbeddingProvider",
    "FakeIngestionUnitOfWorkFactory",
    "FakeChunkSearchRepository",
]
