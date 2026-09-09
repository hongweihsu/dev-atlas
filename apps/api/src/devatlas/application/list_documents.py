from devatlas.application.ports.document_list import (
    DocumentListRepository,
    DocumentSummary,
)


class ListDocuments:
    def __init__(self, repository: DocumentListRepository) -> None:
        self._repository = repository

    async def execute(self) -> list[DocumentSummary]:
        return await self._repository.list_documents()
