from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from retrieval_works.api.routes.workspace_questions import get_answer_workspace_question
from retrieval_works.application.answer_workspace_question import (
    AnswerWorkspaceQuestion,
)
from retrieval_works.application.ports.tool_calling import (
    ExecutedTool,
    WorkspaceQuestionAnswer,
)
from retrieval_works.main import app


@pytest.fixture
def service() -> Iterator[AsyncMock]:
    mocked = AsyncMock(spec=AnswerWorkspaceQuestion)
    app.dependency_overrides[get_answer_workspace_question] = lambda: mocked
    try:
        yield mocked
    finally:
        app.dependency_overrides.clear()


def test_answers_workspace_question_and_exposes_tool_trace(service: AsyncMock) -> None:
    service.execute.return_value = WorkspaceQuestionAnswer(
        text="General contains three documents.",
        tools=(ExecutedTool(name="list_knowledge_bases"),),
    )

    response = TestClient(app).post(
        "/workspace-questions",
        json={"question": "Which knowledge base has the most documents?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "General contains three documents.",
        "tools": [{"name": "list_knowledge_bases"}],
    }
