from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest

from retrieval_works.evaluation.nanobeir_cache import (
    EmbeddingCacheError,
    EmbeddingCacheIdentity,
    NumpyEmbeddingCache,
    embed_records_with_cache,
)


class RecordingEmbeddingProvider:
    model = "test-model"
    dimension = 2

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(len(text)), float(index)] for index, text in enumerate(texts)]


def identity(*, content_sha256: str = "content") -> EmbeddingCacheIdentity:
    return EmbeddingCacheIdentity(
        task_name="NanoExampleRetrieval",
        split="train",
        record_kind="corpus",
        model="test-model",
        dimension=2,
        content_sha256=content_sha256,
    )


async def test_cache_miss_batches_in_stable_id_order_and_then_hits(
    tmp_path: Path,
) -> None:
    provider = RecordingEmbeddingProvider()
    cache = NumpyEmbeddingCache(tmp_path)
    records = {"doc-c": "ccc", "doc-a": "a", "doc-b": "bb"}

    first, first_was_cached = await embed_records_with_cache(
        records=records,
        identity=identity(),
        provider=provider,
        cache=cache,
        batch_size=2,
    )
    second, second_was_cached = await embed_records_with_cache(
        records=records,
        identity=identity(),
        provider=provider,
        cache=cache,
        batch_size=2,
    )

    assert provider.calls == [["a", "bb"], ["ccc"]]
    assert first_was_cached is False
    assert second_was_cached is True
    np.testing.assert_array_equal(first, second)


async def test_changed_content_fingerprint_uses_a_distinct_entry(
    tmp_path: Path,
) -> None:
    provider = RecordingEmbeddingProvider()
    cache = NumpyEmbeddingCache(tmp_path)

    await embed_records_with_cache(
        records={"doc": "one"},
        identity=identity(content_sha256="first"),
        provider=provider,
        cache=cache,
    )
    _, was_cached = await embed_records_with_cache(
        records={"doc": "two"},
        identity=identity(content_sha256="second"),
        provider=provider,
        cache=cache,
    )

    assert was_cached is False
    assert provider.calls == [["one"], ["two"]]


def test_incomplete_cache_entry_fails_closed(tmp_path: Path) -> None:
    cache = NumpyEmbeddingCache(tmp_path)
    selected_identity = identity()
    (tmp_path / f"{selected_identity.key}.json").write_text("{}")

    with pytest.raises(EmbeddingCacheError, match="incomplete"):
        cache.load(selected_identity, ["doc"])
