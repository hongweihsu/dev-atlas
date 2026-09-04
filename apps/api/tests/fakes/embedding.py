from collections.abc import Sequence
from hashlib import sha256
from math import sqrt


class DeterministicEmbeddingProvider:
    """Offline embedding fake with stable, non-zero, unit-length vectors."""

    def __init__(
        self,
        *,
        model: str = "deterministic-test-v1",
        dimension: int = 8,
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be greater than zero")
        self._model = model
        self._dimension = dimension

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        coordinates: list[float] = []
        counter = 0

        while len(coordinates) < self.dimension:
            digest = sha256(f"{counter}:{text}".encode()).digest()
            coordinates.extend((byte - 127.5) / 127.5 for byte in digest)
            counter += 1

        vector = coordinates[: self.dimension]
        magnitude = sqrt(sum(value * value for value in vector))
        return [value / magnitude for value in vector]
