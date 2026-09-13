from collections.abc import Iterator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from devatlas.api.routes.search import get_search_documents
from devatlas.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProviderUnavailableError,
)
from devatlas.application.ports.retrieval import RetrievedChunk
from devatlas.application.search_documents import SearchDocuments
from devatlas.main import app
from tests.fakes import DeterministicEmbeddingProvider, FakeChunkSearchRepository


@pytest.fixture
def search_client() -> Iterator[TestClient]:
    repository = FakeChunkSearchRepository(
        [
            RetrievedChunk(
                document_id=uuid4(),
                document_title="Architecture notes",
                version_id=uuid4(),
                version_number=1,
                chunk_id=uuid4(),
                ordinal=0,
                text="transaction boundaries",
                start_offset=0,
                end_offset=22,
                score=0.91,
                scoring_method="cosine_similarity",
            )
        ]
    )
    service = SearchDocuments(
        embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        repository=repository,
    )
    app.dependency_overrides[get_search_documents] = lambda: service
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_post_search_returns_ranked_chunk_provenance(
    search_client: TestClient,
) -> None:
    response = search_client.post(
        "/search",
        json={"query": "transaction", "limit": 1},
    )

    assert response.status_code == 200
    assert len(response.json()["results"]) == 1
    result = response.json()["results"][0]
    assert result["document_title"] == "Architecture notes"
    assert result["version_number"] == 1
    assert result["ordinal"] == 0
    assert result["text"] == "transaction boundaries"
    assert result["start_offset"] == 0
    assert result["end_offset"] == 22
    assert result["score"] == 0.91
    assert result["scoring_method"] == "cosine_similarity"


def test_post_search_forwards_validated_multi_knowledge_base_scope(
    search_client: TestClient,
) -> None:
    first, second = uuid4(), uuid4()
    manager = AsyncMock()
    manager.resolve_scope.return_value = (first, second)
    app.state.manage_knowledge_bases = manager
    try:
        response = search_client.post(
            "/search",
            json={
                "query": "transaction",
                "knowledge_base_ids": [str(first), str(second)],
            },
        )
    finally:
        del app.state.manage_knowledge_bases

    assert response.status_code == 200
    manager.resolve_scope.assert_awaited_once_with(UUID(int=999), (first, second))


@pytest.mark.parametrize(
    "payload",
    [
        {"query": ""},
        {"query": "   "},
        {"query": "valid", "limit": 0},
        {"query": "valid", "limit": 21},
    ],
)
def test_post_search_maps_invalid_input(
    search_client: TestClient,
    payload: dict[str, object],
) -> None:
    response = search_client.post("/search", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_search"


def test_post_search_reports_unconfigured_runtime() -> None:
    response = TestClient(app).post("/search", json={"query": "transaction"})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "search_unavailable"


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (
            EmbeddingProviderUnavailableError("provider request failed"),
            503,
            "embedding_unavailable",
        ),
        (
            EmbeddingBatchError("invalid provider response"),
            502,
            "invalid_embedding_response",
        ),
    ],
)
def test_post_search_maps_embedding_failures(
    error: Exception,
    expected_status: int,
    expected_code: str,
) -> None:
    service = AsyncMock(spec=SearchDocuments)
    service.execute.side_effect = error
    app.dependency_overrides[get_search_documents] = lambda: service
    try:
        response = TestClient(app).post("/search", json={"query": "transaction"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == expected_status
    assert response.json()["detail"]["code"] == expected_code
