from uuid import UUID

from devatlas.application.ports.document_versions import (
    DocumentVersionRepository,
    DocumentVersionSummary,
)


class ManageDocumentVersions:
    """Expose and switch immutable versions of one logical document."""

    def __init__(self, repository: DocumentVersionRepository) -> None:
        self._repository = repository

    async def list_versions(
        self, document_id: UUID
    ) -> list[DocumentVersionSummary]:
        return await self._repository.list_versions(document_id)

    async def activate_version(self, document_id: UUID, version_id: UUID) -> None:
        await self._repository.activate_version(document_id, version_id)
