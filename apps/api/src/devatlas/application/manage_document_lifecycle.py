from uuid import UUID

from devatlas.application.ports.document_lifecycle import DocumentLifecycleRepository
from devatlas.application.ports.persistence import DocumentNotFoundError


class ManageDocumentLifecycle:
    """Apply reversible lifecycle transitions to a logical document."""

    def __init__(self, repository: DocumentLifecycleRepository) -> None:
        self._repository = repository

    async def archive(self, document_id: UUID) -> None:
        if not await self._repository.archive(document_id):
            raise DocumentNotFoundError(f"document {document_id} was not found")

    async def restore(self, document_id: UUID) -> None:
        if not await self._repository.restore(document_id):
            raise DocumentNotFoundError(f"document {document_id} was not found")
