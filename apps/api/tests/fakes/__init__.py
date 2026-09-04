"""Deterministic test doubles for external dependencies."""

from tests.fakes.embedding import DeterministicEmbeddingProvider
from tests.fakes.persistence import FakeIngestionUnitOfWorkFactory

__all__ = [
    "DeterministicEmbeddingProvider",
    "FakeIngestionUnitOfWorkFactory",
]
