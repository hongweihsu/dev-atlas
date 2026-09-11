from typing import Protocol
from uuid import UUID


class DocumentLifecycleRepository(Protocol):
    async def archive(self, document_id: UUID) -> bool:
        """Archive a document, returning false when its identity does not exist."""
        ...

    async def restore(self, document_id: UUID) -> bool:
        """Restore a document, returning false when its identity does not exist."""
        ...
