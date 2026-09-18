from dataclasses import dataclass
from uuid import UUID

from retrieval_works.application.answer_documents import (
    AnswerDocuments,
    AnswerDocumentsCommand,
    AnswerDocumentsResult,
)
from retrieval_works.application.ports.correction import CorrectiveQueryGenerator


@dataclass(frozen=True, slots=True)
class CorrectiveAnswerDocumentsCommand:
    question: str
    workspace_id: UUID
    limit: int = 5
    knowledge_base_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class CorrectiveAnswerDocumentsResult:
    result: AnswerDocumentsResult
    correction_applied: bool
    corrective_query: str | None


class CorrectiveAnswerDocuments:
    """Retry retrieval once only after the normal answer reports insufficiency."""

    def __init__(
        self,
        *,
        answer_documents: AnswerDocuments,
        query_generator: CorrectiveQueryGenerator,
    ) -> None:
        self._answer_documents = answer_documents
        self._query_generator = query_generator

    async def execute(
        self, command: CorrectiveAnswerDocumentsCommand
    ) -> CorrectiveAnswerDocumentsResult:
        first = await self._answer_documents.execute(
            self._answer_command(command, command.question)
        )
        if first.has_sufficient_evidence:
            return CorrectiveAnswerDocumentsResult(
                result=first,
                correction_applied=False,
                corrective_query=None,
            )

        corrective_query = (
            await self._query_generator.rewrite(command.question, first.answer)
        ).strip()
        if not corrective_query or corrective_query == command.question.strip():
            return CorrectiveAnswerDocumentsResult(
                result=first,
                correction_applied=False,
                corrective_query=None,
            )
        corrected = await self._answer_documents.execute(
            self._answer_command(command, corrective_query)
        )
        return CorrectiveAnswerDocumentsResult(
            result=corrected,
            correction_applied=True,
            corrective_query=corrective_query,
        )

    @staticmethod
    def _answer_command(
        command: CorrectiveAnswerDocumentsCommand, question: str
    ) -> AnswerDocumentsCommand:
        return AnswerDocumentsCommand(
            question=question,
            workspace_id=command.workspace_id,
            limit=command.limit,
            knowledge_base_ids=command.knowledge_base_ids,
        )
