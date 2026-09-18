from dataclasses import dataclass
from typing import TypedDict, cast
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from retrieval_works.application.answer_documents import (
    AnswerDocuments,
    AnswerDocumentsCommand,
    AnswerDocumentsResult,
)
from retrieval_works.application.ports.conversations import (
    ContextualizeQuestionRequest,
    ConversationRepository,
    ConversationSummary,
    ConversationTurn,
    InvalidConversationError,
    QuestionContextualizer,
)

MAX_CONVERSATION_TITLE_CHARACTERS = 120
MAX_CONVERSATION_HISTORY_TURNS = 6


@dataclass(frozen=True, slots=True)
class AskConversationCommand:
    conversation_id: UUID
    workspace_id: UUID
    user_id: UUID
    question: str
    limit: int = 5
    knowledge_base_ids: tuple[UUID, ...] = ()


class _ConversationState(TypedDict, total=False):
    command: AskConversationCommand
    history: tuple[ConversationTurn, ...]
    standalone_question: str
    answer: AnswerDocumentsResult
    saved_turn: ConversationTurn


class ManageConversations:
    """Run a bounded conversational RAG turn through an inspectable graph."""

    def __init__(
        self,
        *,
        repository: ConversationRepository,
        contextualizer: QuestionContextualizer,
        answer_documents: AnswerDocuments,
    ) -> None:
        self._repository = repository
        self._contextualizer = contextualizer
        self._answer_documents = answer_documents

        builder = StateGraph(_ConversationState)
        builder.add_node("load_history", self._load_history)
        builder.add_node("contextualize", self._contextualize)
        builder.add_node("answer", self._answer)
        builder.add_node("persist", self._persist)
        builder.add_edge(START, "load_history")
        builder.add_edge("load_history", "contextualize")
        builder.add_edge("contextualize", "answer")
        builder.add_edge("answer", "persist")
        builder.add_edge("persist", END)
        self._graph = builder.compile()

    async def create(
        self, *, workspace_id: UUID, user_id: UUID, title: str
    ) -> ConversationSummary:
        normalized = " ".join(title.split())
        if not normalized:
            raise InvalidConversationError("conversation title must not be empty")
        if len(normalized) > MAX_CONVERSATION_TITLE_CHARACTERS:
            raise InvalidConversationError(
                f"conversation title must not exceed "
                f"{MAX_CONVERSATION_TITLE_CHARACTERS} characters"
            )
        return await self._repository.create(
            workspace_id=workspace_id, user_id=user_id, title=normalized
        )

    async def list(
        self, *, workspace_id: UUID, user_id: UUID
    ) -> tuple[ConversationSummary, ...]:
        return await self._repository.list(workspace_id=workspace_id, user_id=user_id)

    async def get_turns(
        self, *, conversation_id: UUID, workspace_id: UUID, user_id: UUID
    ) -> tuple[ConversationTurn, ...]:
        return await self._repository.get_turns(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            limit=100,
        )

    async def ask(self, command: AskConversationCommand) -> ConversationTurn:
        if not command.question.strip():
            raise InvalidConversationError("question must not be empty")
        state = await self._graph.ainvoke({"command": command})
        return cast(ConversationTurn, state["saved_turn"])

    async def _load_history(self, state: _ConversationState) -> _ConversationState:
        command = state["command"]
        history = await self._repository.get_turns(
            conversation_id=command.conversation_id,
            workspace_id=command.workspace_id,
            user_id=command.user_id,
            limit=MAX_CONVERSATION_HISTORY_TURNS,
        )
        return {"history": history}

    async def _contextualize(self, state: _ConversationState) -> _ConversationState:
        command = state["command"]
        history = state["history"]
        if not history:
            return {"standalone_question": command.question.strip()}
        standalone = await self._contextualizer.contextualize(
            ContextualizeQuestionRequest(
                question=command.question.strip(), history=history
            )
        )
        return {"standalone_question": standalone}

    async def _answer(self, state: _ConversationState) -> _ConversationState:
        command = state["command"]
        result = await self._answer_documents.execute(
            AnswerDocumentsCommand(
                question=state["standalone_question"],
                workspace_id=command.workspace_id,
                limit=command.limit,
                knowledge_base_ids=command.knowledge_base_ids,
            )
        )
        return {"answer": result}

    async def _persist(self, state: _ConversationState) -> _ConversationState:
        command = state["command"]
        answer = state["answer"]
        turn = await self._repository.append_turn(
            conversation_id=command.conversation_id,
            workspace_id=command.workspace_id,
            user_id=command.user_id,
            question=command.question.strip(),
            standalone_question=state["standalone_question"],
            answer=answer.answer,
            citations=answer.citations,
            has_sufficient_evidence=answer.has_sufficient_evidence,
        )
        return {"saved_turn": turn}
