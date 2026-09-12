from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DocumentVersionSummary:
    version_id: UUID
    version_number: int
    source_filename: str
    media_type: str
    content_checksum: str
    character_count: int
    chunk_count: int
    embedding_model: str
    embedding_dimension: int
    is_active: bool
    created_at: datetime


class DocumentVersionNotFoundError(LookupError):
    """Raised when a version does not belong to the requested document."""


class DocumentVersionRepository(Protocol):
    async def list_versions(
        self, workspace_id: UUID, document_id: UUID
    ) -> list[DocumentVersionSummary]: ...

    async def activate_version(
        self, workspace_id: UUID, document_id: UUID, version_id: UUID
    ) -> None: ...
