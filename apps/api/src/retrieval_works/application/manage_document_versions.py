from uuid import UUID

from retrieval_works.application.ports.document_versions import (
    DocumentVersionRepository,
    DocumentVersionSummary,
)


class ManageDocumentVersions:
    """Expose and switch immutable versions of one logical document."""

    def __init__(self, repository: DocumentVersionRepository) -> None:
        self._repository = repository

    async def list_versions(
        self, workspace_id: UUID, document_id: UUID
    ) -> list[DocumentVersionSummary]:
        return await self._repository.list_versions(workspace_id, document_id)

    async def activate_version(
        self, workspace_id: UUID, document_id: UUID, version_id: UUID
    ) -> None:
        await self._repository.activate_version(workspace_id, document_id, version_id)
