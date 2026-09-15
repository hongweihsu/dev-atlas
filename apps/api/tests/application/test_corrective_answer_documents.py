from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from devatlas.application.answer_documents import AnswerDocuments, AnswerDocumentsResult
from devatlas.application.corrective_answer_documents import (
    CorrectiveAnswerDocuments,
    CorrectiveAnswerDocumentsCommand,
)
from devatlas.application.ports.correction import CorrectiveQueryGenerator

WORKSPACE_ID = UUID(int=999)


def result(*, sufficient: bool, answer: str) -> AnswerDocumentsResult:
    return AnswerDocumentsResult(
        answer=answer,
        citations=(),
        has_sufficient_evidence=sufficient,
    )


@pytest.mark.asyncio
async def test_does_not_pay_for_correction_when_first_answer_is_sufficient() -> None:
    answers = AsyncMock(spec=AnswerDocuments)
    answers.execute.return_value = result(sufficient=True, answer="Supported")
    rewriter = AsyncMock(spec=CorrectiveQueryGenerator)
    service = CorrectiveAnswerDocuments(
        answer_documents=answers, query_generator=rewriter
    )

    output = await service.execute(
        CorrectiveAnswerDocumentsCommand(question="Original", workspace_id=WORKSPACE_ID)
    )

    assert output.result.answer == "Supported"
    assert output.correction_applied is False
    assert output.corrective_query is None
    assert answers.execute.await_count == 1
    rewriter.rewrite.assert_not_awaited()


@pytest.mark.asyncio
async def test_rewrites_and_retries_exactly_once_after_insufficient_answer() -> None:
    answers = AsyncMock(spec=AnswerDocuments)
    answers.execute.side_effect = [
        result(sufficient=False, answer="Insufficient"),
        result(sufficient=True, answer="Corrected"),
    ]
    rewriter = AsyncMock(spec=CorrectiveQueryGenerator)
    rewriter.rewrite.return_value = "database transaction unit of work"
    service = CorrectiveAnswerDocuments(
        answer_documents=answers, query_generator=rewriter
    )

    output = await service.execute(
        CorrectiveAnswerDocumentsCommand(
            question="Why does it matter?",
            workspace_id=WORKSPACE_ID,
            knowledge_base_ids=(UUID(int=1),),
        )
    )

    assert output.result.answer == "Corrected"
    assert output.correction_applied is True
    assert output.corrective_query == "database transaction unit of work"
    assert answers.execute.await_count == 2
    assert answers.execute.await_args_list[1].args[0].question == (
        "database transaction unit of work"
    )
    assert answers.execute.await_args_list[1].args[0].knowledge_base_ids == (
        UUID(int=1),
    )
    rewriter.rewrite.assert_awaited_once_with("Why does it matter?", "Insufficient")


@pytest.mark.asyncio
async def test_identical_rewrite_stops_without_duplicate_retrieval() -> None:
    answers = AsyncMock(spec=AnswerDocuments)
    answers.execute.return_value = result(sufficient=False, answer="Insufficient")
    rewriter = AsyncMock(spec=CorrectiveQueryGenerator)
    rewriter.rewrite.return_value = "Original"
    service = CorrectiveAnswerDocuments(
        answer_documents=answers, query_generator=rewriter
    )

    output = await service.execute(
        CorrectiveAnswerDocumentsCommand(question="Original", workspace_id=WORKSPACE_ID)
    )

    assert output.correction_applied is False
    assert answers.execute.await_count == 1
