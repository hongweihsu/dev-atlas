from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from retrieval_works.application.answer_workspace_question import (
    MAX_WORKSPACE_QUESTION_CHARACTERS,
    AnswerWorkspaceQuestion,
    AnswerWorkspaceQuestionCommand,
)
from retrieval_works.application.ports.tool_calling import (
    InvalidWorkspaceQuestionError,
    WorkspaceQuestionAnswer,
    WorkspaceQuestionAnswerer,
)


@pytest.mark.asyncio
async def test_workspace_question_is_normalized_before_delegation() -> None:
    answerer = AsyncMock(spec=WorkspaceQuestionAnswerer)
    answerer.answer.return_value = WorkspaceQuestionAnswer(text="Two.", tools=())
    workspace_id = uuid4()
    service = AnswerWorkspaceQuestion(answerer)

    result = await service.execute(
        AnswerWorkspaceQuestionCommand(
            question="  How many knowledge bases?  ", workspace_id=workspace_id
        )
    )

    assert result.text == "Two."
    answerer.answer.assert_awaited_once_with(
        "How many knowledge bases?", workspace_id=workspace_id
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question", ["   ", "x" * (MAX_WORKSPACE_QUESTION_CHARACTERS + 1)]
)
async def test_workspace_question_rejects_invalid_input(question: str) -> None:
    answerer = AsyncMock(spec=WorkspaceQuestionAnswerer)
    service = AnswerWorkspaceQuestion(answerer)

    with pytest.raises(InvalidWorkspaceQuestionError):
        await service.execute(
            AnswerWorkspaceQuestionCommand(question=question, workspace_id=uuid4())
        )

    answerer.answer.assert_not_awaited()
