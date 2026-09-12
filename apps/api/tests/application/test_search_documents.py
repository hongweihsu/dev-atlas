from uuid import UUID, uuid4

import pytest

from devatlas.application.ports.retrieval import RetrievedChunk
from devatlas.application.search_documents import (
    MAX_QUERY_CHARACTERS,
    InvalidSearchQueryError,
    SearchDocuments,
    SearchDocumentsCommand,
)
from tests.fakes import DeterministicEmbeddingProvider, FakeChunkSearchRepository

WORKSPACE_ID = UUID(int=999)


def make_result() -> RetrievedChunk:
    return RetrievedChunk(
        document_id=uuid4(),
        document_title="Notes",
        version_id=uuid4(),
        version_number=1,
        chunk_id=uuid4(),
        ordinal=0,
        text="transaction boundary",
        start_offset=0,
        end_offset=20,
        score=0.9,
        scoring_method="cosine_similarity",
    )


@pytest.mark.asyncio
async def test_search_embeds_normalized_query_and_returns_repository_results() -> None:
    expected = make_result()
    repository = FakeChunkSearchRepository([expected])
    provider = DeterministicEmbeddingProvider(dimension=8)
    use_case = SearchDocuments(
        embedding_provider=provider,
        repository=repository,
    )

    results = await use_case.execute(
        SearchDocumentsCommand(query="  transaction  ", workspace_id=WORKSPACE_ID)
    )

    assert results == [expected]
    expected_embedding = (await provider.embed(["transaction"]))[0]
    assert repository.calls == [
        (
            WORKSPACE_ID,
            "transaction",
            tuple(expected_embedding),
            "deterministic-test-v1",
            5,
            "hybrid",
        )
    ]


@pytest.mark.asyncio
async def test_lexical_search_skips_embedding_provider() -> None:
    expected = make_result()
    repository = FakeChunkSearchRepository([expected])
    provider = DeterministicEmbeddingProvider(dimension=8)
    use_case = SearchDocuments(
        embedding_provider=provider,
        repository=repository,
    )

    results = await use_case.execute(
        SearchDocumentsCommand(
            query="DVX-4827", workspace_id=WORKSPACE_ID, strategy="lexical"
        )
    )

    assert results == [expected]
    assert repository.calls == [
        (WORKSPACE_ID, "DVX-4827", None, "deterministic-test-v1", 5, "lexical")
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command", "message"),
    [
        (
            SearchDocumentsCommand(query="  ", workspace_id=WORKSPACE_ID),
            "query must not be empty",
        ),
        (
            SearchDocumentsCommand(
                query="a" * (MAX_QUERY_CHARACTERS + 1),
                workspace_id=WORKSPACE_ID,
            ),
            "query must not exceed",
        ),
        (
            SearchDocumentsCommand(query="valid", workspace_id=WORKSPACE_ID, limit=0),
            "limit must be between",
        ),
        (
            SearchDocumentsCommand(query="valid", workspace_id=WORKSPACE_ID, limit=21),
            "limit must be between",
        ),
    ],
)
async def test_search_rejects_invalid_input_before_external_work(
    command: SearchDocumentsCommand,
    message: str,
) -> None:
    repository = FakeChunkSearchRepository()
    use_case = SearchDocuments(
        embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        repository=repository,
    )

    with pytest.raises(InvalidSearchQueryError, match=message):
        await use_case.execute(command)

    assert repository.calls == []
