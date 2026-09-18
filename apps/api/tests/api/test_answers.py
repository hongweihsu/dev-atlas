from collections.abc import Iterator
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from retrieval_works.api.routes.answers import get_answer_documents
from retrieval_works.application.answer_documents import (
    AnswerDocuments,
    AnswerDocumentsResult,
)
from retrieval_works.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProviderUnavailableError,
)
from retrieval_works.application.ports.generation import (
    AnswerGeneratorUnavailableError,
    EvidenceSource,
    InvalidGeneratedAnswerError,
)
from retrieval_works.application.search_documents import InvalidSearchQueryError
from retrieval_works.main import app


def make_citation() -> EvidenceSource:
    return EvidenceSource(
        citation_id="S1",
        document_id=uuid4(),
        document_title="Architecture notes",
        version_id=uuid4(),
        version_number=1,
        chunk_id=uuid4(),
        ordinal=3,
        text="A unit of work defines a transaction boundary.",
        start_offset=100,
        end_offset=146,
    )


@pytest.fixture
def answer_service() -> Iterator[AsyncMock]:
    service = AsyncMock(spec=AnswerDocuments)
    service.execute.return_value = AnswerDocumentsResult(
        answer="It defines a transaction boundary. [S1]",
        citations=(make_citation(),),
        has_sufficient_evidence=True,
    )
    app.dependency_overrides[get_answer_documents] = lambda: service
    try:
        yield service
    finally:
        app.dependency_overrides.clear()


def test_post_answers_returns_answer_and_citation_provenance(
    answer_service: AsyncMock,
) -> None:
    response = TestClient(app).post(
        "/answers",
        json={"question": "What is a unit of work?", "limit": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "It defines a transaction boundary. [S1]"
    assert payload["has_sufficient_evidence"] is True
    assert len(payload["citations"]) == 1
    assert payload["citations"][0]["citation_id"] == "S1"
    assert payload["citations"][0]["document_title"] == "Architecture notes"
    assert payload["citations"][0]["start_offset"] == 100
    command = answer_service.execute.await_args.args[0]
    assert command.question == "What is a unit of work?"
    assert command.limit == 3


def test_post_answers_reports_unconfigured_runtime() -> None:
    response = TestClient(app).post("/answers", json={"question": "What is it?"})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "answers_unavailable"


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (InvalidSearchQueryError("invalid"), 422, "invalid_question"),
        (EmbeddingBatchError("invalid"), 502, "invalid_embedding_response"),
        (InvalidGeneratedAnswerError("invalid"), 502, "invalid_answer_response"),
        (
            EmbeddingProviderUnavailableError("unavailable"),
            503,
            "embedding_unavailable",
        ),
        (
            AnswerGeneratorUnavailableError("unavailable"),
            503,
            "answer_provider_unavailable",
        ),
    ],
)
def test_post_answers_maps_application_failures(
    error: Exception,
    expected_status: int,
    expected_code: str,
) -> None:
    service = AsyncMock(spec=AnswerDocuments)
    service.execute.side_effect = error
    app.dependency_overrides[get_answer_documents] = lambda: service
    try:
        response = TestClient(app).post(
            "/answers",
            json={"question": "What is it?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == expected_status
    assert response.json()["detail"]["code"] == expected_code
