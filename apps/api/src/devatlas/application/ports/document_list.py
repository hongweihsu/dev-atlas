from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

type DocumentListStatus = Literal["active", "archived"]


@dataclass(frozen=True, slots=True)
class DocumentSummary:
    document_id: UUID
    title: str
    active_version_id: UUID
    active_version_number: int
    source_filename: str
    chunk_count: int
    updated_at: datetime
    archived_at: datetime | None


class DocumentListRepository(Protocol):
    async def list_documents(
        self, *, workspace_id: UUID, status: DocumentListStatus
    ) -> list[DocumentSummary]:
        """Return filtered documents with their current version summaries."""
        ...
