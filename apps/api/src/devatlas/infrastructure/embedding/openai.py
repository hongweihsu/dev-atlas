from collections.abc import Sequence

from openai import AsyncOpenAI, OpenAIError

from devatlas.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProviderUnavailableError,
)


class OpenAIEmbeddingProvider:
    """Generate ordered float embeddings through the OpenAI API."""

    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be empty")
        if dimension <= 0:
            raise ValueError("dimension must be greater than zero")
        self._client = client
        self._model = model
        self._dimension = dimension

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=list(texts),
                dimensions=self.dimension,
                encoding_format="float",
            )
        except OpenAIError as error:
            raise EmbeddingProviderUnavailableError(
                "embedding provider request failed"
            ) from error

        ordered = sorted(response.data, key=lambda item: item.index)
        indices = [item.index for item in ordered]
        if indices != list(range(len(texts))):
            raise EmbeddingBatchError(
                "embedding provider returned incompatible result indices"
            )
        return [list(item.embedding) for item in ordered]
