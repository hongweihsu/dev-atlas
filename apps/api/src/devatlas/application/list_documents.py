from uuid import UUID

from devatlas.application.ports.document_list import (
    DocumentListRepository,
    DocumentListStatus,
    DocumentSummary,
)


class ListDocuments:
    def __init__(self, repository: DocumentListRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        workspace_id: UUID,
        status: DocumentListStatus = "active",
        knowledge_base_ids: tuple[UUID, ...] = (),
    ) -> list[DocumentSummary]:
        return await self._repository.list_documents(
            workspace_id=workspace_id,
            status=status,
            knowledge_base_ids=knowledge_base_ids,
        )
