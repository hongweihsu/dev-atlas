from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from devatlas.application.ports.generation import EvidenceSource


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    id: UUID
    conversation_id: UUID
    ordinal: int
    question: str
    standalone_question: str
    answer: str
    citations: tuple[EvidenceSource, ...]
    has_sufficient_evidence: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ContextualizeQuestionRequest:
    question: str
    history: tuple[ConversationTurn, ...]


class ConversationRepository(Protocol):
    async def create(
        self, *, workspace_id: UUID, user_id: UUID, title: str
    ) -> ConversationSummary: ...

    async def list(
        self, *, workspace_id: UUID, user_id: UUID
    ) -> tuple[ConversationSummary, ...]: ...

    async def get_turns(
        self,
        *,
        conversation_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        limit: int,
    ) -> tuple[ConversationTurn, ...]: ...

    async def append_turn(
        self,
        *,
        conversation_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        question: str,
        standalone_question: str,
        answer: str,
        citations: tuple[EvidenceSource, ...],
        has_sufficient_evidence: bool,
    ) -> ConversationTurn: ...


class QuestionContextualizer(Protocol):
    async def contextualize(self, request: ContextualizeQuestionRequest) -> str: ...


class ConversationNotFoundError(LookupError):
    """Raised when a conversation is absent or outside the caller's scope."""


class InvalidConversationError(ValueError):
    """Raised when conversation input violates a bounded contract."""


class QuestionContextualizerUnavailableError(RuntimeError):
    """Raised when a follow-up question cannot be contextualized."""
