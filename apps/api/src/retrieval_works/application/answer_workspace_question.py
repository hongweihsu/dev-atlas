from dataclasses import dataclass
from uuid import UUID

from retrieval_works.application.ports.tool_calling import (
    InvalidWorkspaceQuestionError,
    WorkspaceQuestionAnswer,
    WorkspaceQuestionAnswerer,
)

MAX_WORKSPACE_QUESTION_CHARACTERS = 2_000


@dataclass(frozen=True, slots=True)
class AnswerWorkspaceQuestionCommand:
    question: str
    workspace_id: UUID


class AnswerWorkspaceQuestion:
    def __init__(self, answerer: WorkspaceQuestionAnswerer) -> None:
        self._answerer = answerer

    async def execute(
        self, command: AnswerWorkspaceQuestionCommand
    ) -> WorkspaceQuestionAnswer:
        question = command.question.strip()
        if not question:
            raise InvalidWorkspaceQuestionError("question must not be empty")
        if len(question) > MAX_WORKSPACE_QUESTION_CHARACTERS:
            raise InvalidWorkspaceQuestionError(
                "question must not exceed "
                f"{MAX_WORKSPACE_QUESTION_CHARACTERS} characters"
            )
        return await self._answerer.answer(question, workspace_id=command.workspace_id)
