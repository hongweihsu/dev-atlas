from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from retrieval_works.application.ports.knowledge_bases import (
    DuplicateKnowledgeBaseNameError,
    KnowledgeBaseSummary,
)
from retrieval_works.infrastructure.models import Document, KnowledgeBase
from retrieval_works.infrastructure.persistence.unit_of_work import SessionFactory


class SqlAlchemyKnowledgeBaseRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def list(self, workspace_id: UUID) -> list[KnowledgeBaseSummary]:
        statement = (
            select(
                KnowledgeBase.id,
                KnowledgeBase.name,
                KnowledgeBase.is_default,
                func.count(Document.id).label("document_count"),
            )
            .outerjoin(Document, Document.knowledge_base_id == KnowledgeBase.id)
            .where(KnowledgeBase.workspace_id == workspace_id)
            .group_by(KnowledgeBase.id)
            .order_by(
                KnowledgeBase.is_default.desc(), KnowledgeBase.name, KnowledgeBase.id
            )
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).all()
        return [
            KnowledgeBaseSummary(
                id=row.id,
                name=row.name,
                is_default=row.is_default,
                document_count=row.document_count,
            )
            for row in rows
        ]

    async def create(self, workspace_id: UUID, name: str) -> KnowledgeBaseSummary:
        knowledge_base = KnowledgeBase(
            workspace_id=workspace_id,
            name=name,
            is_default=False,
        )
        try:
            async with self._session_factory() as session:
                session.add(knowledge_base)
                await session.commit()
                await session.refresh(knowledge_base)
        except IntegrityError as error:
            raise DuplicateKnowledgeBaseNameError(
                "a knowledge base with this name already exists"
            ) from error
        return KnowledgeBaseSummary(
            id=knowledge_base.id,
            name=knowledge_base.name,
            is_default=knowledge_base.is_default,
            document_count=0,
        )

    async def resolve_scope(
        self, workspace_id: UUID, requested_ids: tuple[UUID, ...]
    ) -> tuple[UUID, ...]:
        statement = select(KnowledgeBase.id).where(
            KnowledgeBase.workspace_id == workspace_id
        )
        if requested_ids:
            statement = statement.where(KnowledgeBase.id.in_(set(requested_ids)))
        statement = statement.order_by(KnowledgeBase.id)
        async with self._session_factory() as session:
            return tuple((await session.scalars(statement)).all())
