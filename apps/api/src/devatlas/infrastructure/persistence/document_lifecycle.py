from uuid import UUID

from sqlalchemy import func, select, update

from devatlas.infrastructure.models import Document
from devatlas.infrastructure.persistence.unit_of_work import SessionFactory


class SqlAlchemyDocumentLifecycleRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def archive(self, workspace_id: UUID, document_id: UUID) -> bool:
        return await self._set_archived(workspace_id, document_id, archived=True)

    async def restore(self, workspace_id: UUID, document_id: UUID) -> bool:
        return await self._set_archived(workspace_id, document_id, archived=False)

    async def _set_archived(
        self, workspace_id: UUID, document_id: UUID, *, archived: bool
    ) -> bool:
        async with self._session_factory() as session, session.begin():
            exists = await session.scalar(
                select(Document.id)
                .where(
                    Document.id == document_id,
                    Document.workspace_id == workspace_id,
                )
                .with_for_update()
            )
            if exists is None:
                return False
            await session.execute(
                update(Document)
                .where(
                    Document.id == document_id,
                    Document.workspace_id == workspace_id,
                )
                .values(
                    archived_at=func.now() if archived else None,
                    updated_at=func.now(),
                )
            )
        return True
