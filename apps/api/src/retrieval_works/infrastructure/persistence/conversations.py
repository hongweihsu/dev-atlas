from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from retrieval_works.application.ports.conversations import (
    ConversationNotFoundError,
    ConversationRepository,
    ConversationSummary,
    ConversationTurn,
)
from retrieval_works.application.ports.generation import EvidenceSource
from retrieval_works.infrastructure.models.conversation import (
    Conversation,
    ConversationTurnModel,
)


def _source_to_json(source: EvidenceSource) -> dict[str, object]:
    return {
        "citation_id": source.citation_id,
        "document_id": str(source.document_id),
        "document_title": source.document_title,
        "version_id": str(source.version_id),
        "version_number": source.version_number,
        "chunk_id": str(source.chunk_id),
        "ordinal": source.ordinal,
        "text": source.text,
        "start_offset": source.start_offset,
        "end_offset": source.end_offset,
        "page_start": source.page_start,
        "page_end": source.page_end,
    }


def _source_from_json(value: dict[str, Any]) -> EvidenceSource:
    return EvidenceSource(
        citation_id=str(value["citation_id"]),
        document_id=UUID(str(value["document_id"])),
        document_title=str(value["document_title"]),
        version_id=UUID(str(value["version_id"])),
        version_number=int(value["version_number"]),
        chunk_id=UUID(str(value["chunk_id"])),
        ordinal=int(value["ordinal"]),
        text=str(value["text"]),
        start_offset=int(value["start_offset"]),
        end_offset=int(value["end_offset"]),
        page_start=(
            int(value["page_start"]) if value.get("page_start") is not None else None
        ),
        page_end=(
            int(value["page_end"]) if value.get("page_end") is not None else None
        ),
    )


def _summary(model: Conversation) -> ConversationSummary:
    return ConversationSummary(
        id=model.id,
        title=model.title,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _turn(model: ConversationTurnModel) -> ConversationTurn:
    return ConversationTurn(
        id=model.id,
        conversation_id=model.conversation_id,
        ordinal=model.ordinal,
        question=model.question,
        standalone_question=model.standalone_question,
        answer=model.answer,
        citations=tuple(_source_from_json(item) for item in model.citations),
        has_sufficient_evidence=model.has_sufficient_evidence,
        created_at=model.created_at,
    )


class SqlAlchemyConversationRepository(ConversationRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(
        self, *, workspace_id: UUID, user_id: UUID, title: str
    ) -> ConversationSummary:
        async with self._session_factory() as session, session.begin():
            model = Conversation(
                workspace_id=workspace_id,
                user_id=user_id,
                title=title,
            )
            session.add(model)
            await session.flush()
            await session.refresh(model)
            return _summary(model)

    async def list(
        self, *, workspace_id: UUID, user_id: UUID
    ) -> tuple[ConversationSummary, ...]:
        async with self._session_factory() as session:
            models = (
                await session.scalars(
                    select(Conversation)
                    .where(
                        Conversation.workspace_id == workspace_id,
                        Conversation.user_id == user_id,
                    )
                    .order_by(Conversation.updated_at.desc(), Conversation.id)
                )
            ).all()
            return tuple(_summary(model) for model in models)

    async def get_turns(
        self,
        *,
        conversation_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        limit: int,
    ) -> tuple[ConversationTurn, ...]:
        async with self._session_factory() as session:
            await self._require_conversation(
                session,
                conversation_id=conversation_id,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            models = list(
                (
                    await session.scalars(
                        select(ConversationTurnModel)
                        .where(ConversationTurnModel.conversation_id == conversation_id)
                        .order_by(ConversationTurnModel.ordinal.desc())
                        .limit(limit)
                    )
                ).all()
            )
            models.reverse()
            return tuple(_turn(model) for model in models)

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
    ) -> ConversationTurn:
        async with self._session_factory() as session, session.begin():
            conversation = await self._require_conversation(
                session,
                conversation_id=conversation_id,
                workspace_id=workspace_id,
                user_id=user_id,
                for_update=True,
            )
            highest = await session.scalar(
                select(func.max(ConversationTurnModel.ordinal)).where(
                    ConversationTurnModel.conversation_id == conversation_id
                )
            )
            model = ConversationTurnModel(
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                ordinal=0 if highest is None else highest + 1,
                question=question,
                standalone_question=standalone_question,
                answer=answer,
                citations=[_source_to_json(item) for item in citations],
                has_sufficient_evidence=has_sufficient_evidence,
            )
            conversation.updated_at = datetime.now(UTC)
            session.add(model)
            await session.flush()
            await session.refresh(model)
            return _turn(model)

    @staticmethod
    async def _require_conversation(
        session: AsyncSession,
        *,
        conversation_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        for_update: bool = False,
    ) -> Conversation:
        statement = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
            Conversation.user_id == user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await session.scalar(statement)
        if model is None:
            raise ConversationNotFoundError("conversation not found")
        return model
