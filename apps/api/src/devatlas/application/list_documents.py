from devatlas.application.ports.catalog import (
    DocumentCatalogRepository,
    DocumentSummary,
)


class ListDocuments:
    def __init__(self, repository: DocumentCatalogRepository) -> None:
        self._repository = repository

    async def execute(self) -> list[DocumentSummary]:
        return await self._repository.list_documents()
