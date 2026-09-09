from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DocumentSummary:
    document_id: UUID
    title: str
    active_version_id: UUID
    active_version_number: int
    source_filename: str
    chunk_count: int
    updated_at: datetime


class DocumentListRepository(Protocol):
    async def list_documents(self) -> list[DocumentSummary]:
        """Return logical documents with their active version summaries."""
        ...
