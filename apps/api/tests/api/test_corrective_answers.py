from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from devatlas.api.routes.corrective_answers import get_corrective_answer_documents
from devatlas.application.answer_documents import AnswerDocumentsResult
from devatlas.application.corrective_answer_documents import (
    CorrectiveAnswerDocuments,
    CorrectiveAnswerDocumentsResult,
)
from devatlas.main import app


@pytest.fixture
def service() -> Iterator[AsyncMock]:
    mocked = AsyncMock(spec=CorrectiveAnswerDocuments)
    app.dependency_overrides[get_corrective_answer_documents] = lambda: mocked
    try:
        yield mocked
    finally:
        app.dependency_overrides.clear()


def test_exposes_whether_a_corrective_query_was_used(service: AsyncMock) -> None:
    service.execute.return_value = CorrectiveAnswerDocumentsResult(
        result=AnswerDocumentsResult(
            answer="Corrected answer",
            citations=(),
            has_sufficient_evidence=False,
        ),
        correction_applied=True,
        corrective_query="transaction boundary unit of work",
    )

    response = TestClient(app).post(
        "/corrective-answers",
        json={"question": "Why does it matter?", "knowledge_base_ids": []},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Corrected answer",
        "has_sufficient_evidence": False,
        "citations": [],
        "correction_applied": True,
        "corrective_query": "transaction boundary unit of work",
    }
