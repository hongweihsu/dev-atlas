from math import inf, isclose, nan, sqrt

import pytest

from devatlas.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProvider,
    validate_embedding_batch,
)
from tests.fakes import DeterministicEmbeddingProvider


def accepts_embedding_provider(provider: EmbeddingProvider) -> EmbeddingProvider:
    """Compile-time assertion that the fake satisfies the application protocol."""
    return provider


@pytest.mark.asyncio
async def test_deterministic_provider_preserves_count_order_and_shape() -> None:
    provider = accepts_embedding_provider(DeterministicEmbeddingProvider(dimension=8))

    first = await provider.embed(["alpha", "beta"])
    second = await provider.embed(["alpha", "beta"])

    assert first == second
    assert len(first) == 2
    assert first[0] != first[1]
    assert all(len(embedding) == 8 for embedding in first)
    assert all(
        isclose(sqrt(sum(value * value for value in embedding)), 1.0)
        for embedding in first
    )


def test_validate_embedding_batch_accepts_compatible_finite_vectors() -> None:
    validate_embedding_batch(
        [[0.1, 0.2], [-0.3, 0.4]],
        expected_count=2,
        expected_dimension=2,
    )


def test_validate_embedding_batch_rejects_wrong_count() -> None:
    with pytest.raises(
        EmbeddingBatchError,
        match="expected 2 embeddings, received 1",
    ):
        validate_embedding_batch(
            [[0.1, 0.2]],
            expected_count=2,
            expected_dimension=2,
        )


def test_validate_embedding_batch_rejects_wrong_dimension() -> None:
    with pytest.raises(
        EmbeddingBatchError,
        match="embedding 0 has dimension 1; expected 2",
    ):
        validate_embedding_batch(
            [[0.1]],
            expected_count=1,
            expected_dimension=2,
        )


@pytest.mark.parametrize("invalid_value", [nan, inf, -inf])
def test_validate_embedding_batch_rejects_non_finite_values(
    invalid_value: float,
) -> None:
    with pytest.raises(
        EmbeddingBatchError,
        match="embedding 0 contains a non-finite value",
    ):
        validate_embedding_batch(
            [[0.1, invalid_value]],
            expected_count=1,
            expected_dimension=2,
        )


@pytest.mark.parametrize(
    ("expected_count", "expected_dimension", "message"),
    [
        (-1, 2, "expected_count must not be negative"),
        (0, 0, "expected_dimension must be greater than zero"),
    ],
)
def test_validate_embedding_batch_rejects_invalid_expectations(
    expected_count: int,
    expected_dimension: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_embedding_batch(
            [],
            expected_count=expected_count,
            expected_dimension=expected_dimension,
        )
