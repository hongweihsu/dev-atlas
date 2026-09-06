from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import APIConnectionError, AsyncOpenAI

from devatlas.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProvider,
    EmbeddingProviderUnavailableError,
)
from devatlas.infrastructure.embedding import OpenAIEmbeddingProvider


def make_client() -> tuple[AsyncOpenAI, AsyncMock]:
    create = AsyncMock()
    client = MagicMock(spec=AsyncOpenAI)
    client.embeddings.create = create
    return cast(AsyncOpenAI, client), create


def accepts_embedding_provider(provider: EmbeddingProvider) -> EmbeddingProvider:
    return provider


@pytest.mark.asyncio
async def test_openai_provider_requests_ordered_float_embeddings() -> None:
    client, create = make_client()
    create.return_value = SimpleNamespace(
        data=[
            SimpleNamespace(index=1, embedding=[0.3, 0.4]),
            SimpleNamespace(index=0, embedding=[0.1, 0.2]),
        ]
    )
    provider = OpenAIEmbeddingProvider(
        client,
        model="text-embedding-3-small",
        dimension=2,
    )

    embeddings = await accepts_embedding_provider(provider).embed(["first", "second"])

    assert embeddings == [[0.1, 0.2], [0.3, 0.4]]
    create.assert_awaited_once_with(
        model="text-embedding-3-small",
        input=["first", "second"],
        dimensions=2,
        encoding_format="float",
    )


@pytest.mark.asyncio
async def test_openai_provider_does_not_call_api_for_empty_batch() -> None:
    client, create = make_client()
    provider = OpenAIEmbeddingProvider(client)

    assert await provider.embed([]) == []
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_openai_provider_rejects_incompatible_indices() -> None:
    client, create = make_client()
    create.return_value = SimpleNamespace(
        data=[SimpleNamespace(index=1, embedding=[0.1, 0.2])]
    )
    provider = OpenAIEmbeddingProvider(client, dimension=2)

    with pytest.raises(EmbeddingBatchError, match="result indices"):
        await provider.embed(["only input"])


@pytest.mark.asyncio
async def test_openai_provider_translates_sdk_failure() -> None:
    client, create = make_client()
    create.side_effect = APIConnectionError(request=MagicMock())
    provider = OpenAIEmbeddingProvider(client)

    with pytest.raises(
        EmbeddingProviderUnavailableError,
        match="provider request failed",
    ):
        await provider.embed(["input"])


@pytest.mark.parametrize(
    ("model", "dimension", "message"),
    [("  ", 1536, "model"), ("text-embedding-3-small", 0, "dimension")],
)
def test_openai_provider_rejects_invalid_configuration(
    model: str,
    dimension: int,
    message: str,
) -> None:
    client, _ = make_client()

    with pytest.raises(ValueError, match=message):
        OpenAIEmbeddingProvider(client, model=model, dimension=dimension)
