from uuid import UUID

from retrieval_works.application.ports.document_lifecycle import (
    DocumentLifecycleRepository,
)
from retrieval_works.application.ports.persistence import DocumentNotFoundError


class ManageDocumentLifecycle:
    """Apply reversible lifecycle transitions to a logical document."""

    def __init__(self, repository: DocumentLifecycleRepository) -> None:
        self._repository = repository

    async def archive(self, workspace_id: UUID, document_id: UUID) -> None:
        if not await self._repository.archive(workspace_id, document_id):
            raise DocumentNotFoundError(f"document {document_id} was not found")

    async def restore(self, workspace_id: UUID, document_id: UUID) -> None:
        if not await self._repository.restore(workspace_id, document_id):
            raise DocumentNotFoundError(f"document {document_id} was not found")
