from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from devatlas.application.answer_documents import AnswerDocuments, AnswerDocumentsResult
from devatlas.application.manage_conversations import (
    MAX_CONVERSATION_HISTORY_TURNS,
    AskConversationCommand,
    ManageConversations,
)
from devatlas.application.ports.conversations import (
    ConversationSummary,
    ConversationTurn,
    QuestionContextualizer,
)

WORKSPACE_ID = UUID(int=999)
USER_ID = UUID(int=998)


class FakeConversationRepository:
    def __init__(self, history: tuple[ConversationTurn, ...] = ()) -> None:
        self.history = history
        self.history_limit: int | None = None
        self.appended: dict[str, object] | None = None

    async def create(
        self, *, workspace_id: UUID, user_id: UUID, title: str
    ) -> ConversationSummary:
        now = datetime.now(UTC)
        return ConversationSummary(uuid4(), title, now, now)

    async def list(
        self, *, workspace_id: UUID, user_id: UUID
    ) -> tuple[ConversationSummary, ...]:
        return ()

    async def get_turns(
        self,
        *,
        conversation_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        limit: int,
    ) -> tuple[ConversationTurn, ...]:
        self.history_limit = limit
        return self.history[-limit:]

    async def append_turn(self, **values: object) -> ConversationTurn:
        self.appended = values
        return ConversationTurn(
            id=uuid4(),
            conversation_id=values["conversation_id"],  # type: ignore[arg-type]
            ordinal=len(self.history),
            question=str(values["question"]),
            standalone_question=str(values["standalone_question"]),
            answer=str(values["answer"]),
            citations=values["citations"],  # type: ignore[arg-type]
            has_sufficient_evidence=bool(values["has_sufficient_evidence"]),
            created_at=datetime.now(UTC),
        )


def make_turn(ordinal: int) -> ConversationTurn:
    return ConversationTurn(
        id=uuid4(),
        conversation_id=UUID(int=500),
        ordinal=ordinal,
        question=f"Question {ordinal}",
        standalone_question=f"Standalone {ordinal}",
        answer=f"Answer {ordinal}",
        citations=(),
        has_sufficient_evidence=True,
        created_at=datetime.now(UTC),
    )


def make_service(
    history: tuple[ConversationTurn, ...] = (),
) -> tuple[
    ManageConversations,
    FakeConversationRepository,
    AsyncMock,
    AsyncMock,
]:
    repository = FakeConversationRepository(history)
    contextualizer = AsyncMock(spec=QuestionContextualizer)
    contextualizer.contextualize.return_value = "What is Terraform state?"
    answers = AsyncMock(spec=AnswerDocuments)
    answers.execute.return_value = AnswerDocumentsResult(
        answer="Terraform state tracks managed resources.",
        citations=(),
        has_sufficient_evidence=False,
    )
    return (
        ManageConversations(
            repository=repository,
            contextualizer=contextualizer,
            answer_documents=answers,
        ),
        repository,
        contextualizer,
        answers,
    )


@pytest.mark.asyncio
async def test_first_turn_skips_contextualization_and_persists_answer() -> None:
    service, repository, contextualizer, answers = make_service()
    conversation_id = uuid4()

    turn = await service.ask(
        AskConversationCommand(
            conversation_id=conversation_id,
            workspace_id=WORKSPACE_ID,
            user_id=USER_ID,
            question="  What is Terraform?  ",
        )
    )

    contextualizer.contextualize.assert_not_awaited()
    assert answers.execute.await_args.args[0].question == "What is Terraform?"
    assert repository.appended is not None
    assert repository.appended["standalone_question"] == "What is Terraform?"
    assert turn.ordinal == 0


@pytest.mark.asyncio
async def test_follow_up_uses_only_bounded_history_and_stores_rewrite() -> None:
    history = tuple(make_turn(index) for index in range(10))
    service, repository, contextualizer, answers = make_service(history)

    turn = await service.ask(
        AskConversationCommand(
            conversation_id=UUID(int=500),
            workspace_id=WORKSPACE_ID,
            user_id=USER_ID,
            question="Why does it matter?",
        )
    )

    request = contextualizer.contextualize.await_args.args[0]
    assert repository.history_limit == MAX_CONVERSATION_HISTORY_TURNS
    assert [item.ordinal for item in request.history] == [4, 5, 6, 7, 8, 9]
    assert answers.execute.await_args.args[0].question == "What is Terraform state?"
    assert turn.standalone_question == "What is Terraform state?"
