from collections.abc import Sequence
from math import isfinite
from typing import Protocol

type EmbeddingVector = Sequence[float]


class EmbeddingProvider(Protocol):
    """Provider-independent contract for ordered batches of text embeddings."""

    @property
    def model(self) -> str:
        """Return the persisted model identifier."""
        ...

    @property
    def dimension(self) -> int:
        """Return the number of coordinates produced for each input."""
        ...

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed each input exactly once while preserving input order."""
        ...


class EmbeddingBatchError(ValueError):
    """Raised when a provider returns an incompatible embedding batch."""


def validate_embedding_batch(
    embeddings: Sequence[EmbeddingVector],
    *,
    expected_count: int,
    expected_dimension: int,
) -> None:
    """Reject provider output that cannot be safely persisted or correlated."""
    if expected_count < 0:
        raise ValueError("expected_count must not be negative")
    if expected_dimension <= 0:
        raise ValueError("expected_dimension must be greater than zero")
    if len(embeddings) != expected_count:
        raise EmbeddingBatchError(
            f"expected {expected_count} embeddings, received {len(embeddings)}"
        )

    for index, embedding in enumerate(embeddings):
        if len(embedding) != expected_dimension:
            raise EmbeddingBatchError(
                f"embedding {index} has dimension {len(embedding)}; "
                f"expected {expected_dimension}"
            )
        if not all(isfinite(value) for value in embedding):
            raise EmbeddingBatchError(f"embedding {index} contains a non-finite value")
