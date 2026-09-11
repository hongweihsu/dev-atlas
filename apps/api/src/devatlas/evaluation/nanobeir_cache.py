from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from devatlas.application.ports.embedding import (
    EmbeddingProvider,
    validate_embedding_batch,
)


class EmbeddingCacheError(RuntimeError):
    """Raised when an existing cache entry is incomplete or incompatible."""


@dataclass(frozen=True, slots=True)
class EmbeddingCacheIdentity:
    task_name: str
    split: str
    record_kind: str
    model: str
    dimension: int
    content_sha256: str

    @property
    def key(self) -> str:
        payload = json.dumps(
            asdict(self), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return sha256(payload).hexdigest()


class NumpyEmbeddingCache:
    """Persist float32 benchmark vectors with a validated JSON manifest."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def load(
        self,
        identity: EmbeddingCacheIdentity,
        record_ids: Sequence[str],
    ) -> NDArray[np.float32] | None:
        manifest_path, vectors_path = self._paths(identity)
        if not manifest_path.exists() and not vectors_path.exists():
            return None
        if not manifest_path.exists() or not vectors_path.exists():
            raise EmbeddingCacheError("cache entry is incomplete")

        manifest = cast(dict[str, Any], json.loads(manifest_path.read_text()))
        if manifest.get("identity") != asdict(identity):
            raise EmbeddingCacheError("cache identity does not match")
        if manifest.get("record_ids") != list(record_ids):
            raise EmbeddingCacheError("cache record order does not match")

        vectors = cast(NDArray[np.float32], np.load(vectors_path, allow_pickle=False))
        expected_shape = (len(record_ids), identity.dimension)
        if vectors.dtype != np.float32 or vectors.shape != expected_shape:
            raise EmbeddingCacheError("cache vector shape or dtype does not match")
        if not np.isfinite(vectors).all():
            raise EmbeddingCacheError("cache contains a non-finite value")
        return vectors

    def store(
        self,
        identity: EmbeddingCacheIdentity,
        record_ids: Sequence[str],
        vectors: NDArray[np.float32],
    ) -> None:
        expected_shape = (len(record_ids), identity.dimension)
        if vectors.dtype != np.float32 or vectors.shape != expected_shape:
            raise EmbeddingCacheError("refusing to store incompatible vectors")
        if not np.isfinite(vectors).all():
            raise EmbeddingCacheError("refusing to store non-finite vectors")

        self._directory.mkdir(parents=True, exist_ok=True)
        manifest_path, vectors_path = self._paths(identity)
        temporary_vectors = vectors_path.with_suffix(".npy.tmp")
        temporary_manifest = manifest_path.with_suffix(".json.tmp")
        with temporary_vectors.open("wb") as file:
            np.save(file, vectors, allow_pickle=False)
        temporary_vectors.replace(vectors_path)
        temporary_manifest.write_text(
            json.dumps(
                {"identity": asdict(identity), "record_ids": list(record_ids)},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary_manifest.replace(manifest_path)

    def _paths(self, identity: EmbeddingCacheIdentity) -> tuple[Path, Path]:
        stem = identity.key
        return self._directory / f"{stem}.json", self._directory / f"{stem}.npy"


async def embed_records_with_cache(
    *,
    records: Mapping[str, str],
    identity: EmbeddingCacheIdentity,
    provider: EmbeddingProvider,
    cache: NumpyEmbeddingCache,
    batch_size: int = 128,
) -> tuple[NDArray[np.float32], bool]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    if provider.model != identity.model or provider.dimension != identity.dimension:
        raise ValueError("provider and cache identity are incompatible")

    record_ids = sorted(records)
    cached = cache.load(identity, record_ids)
    if cached is not None:
        return cached, True

    vectors: list[list[float]] = []
    for start in range(0, len(record_ids), batch_size):
        batch_ids = record_ids[start : start + batch_size]
        batch = await provider.embed([records[record_id] for record_id in batch_ids])
        validate_embedding_batch(
            batch,
            expected_count=len(batch_ids),
            expected_dimension=provider.dimension,
        )
        vectors.extend(batch)

    array = np.asarray(vectors, dtype=np.float32).reshape(
        len(record_ids), identity.dimension
    )
    cache.store(identity, record_ids, array)
    return array, False
