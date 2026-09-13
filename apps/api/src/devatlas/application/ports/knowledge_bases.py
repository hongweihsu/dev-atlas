from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class KnowledgeBaseSummary:
    id: UUID
    name: str
    is_default: bool
    document_count: int


class DuplicateKnowledgeBaseNameError(ValueError):
    """Raised when a workspace already has a knowledge base with this name."""


class InvalidKnowledgeBaseScopeError(ValueError):
    """Raised when requested knowledge bases are outside the workspace."""


class KnowledgeBaseRepository(Protocol):
    async def list(self, workspace_id: UUID) -> list[KnowledgeBaseSummary]: ...

    async def create(self, workspace_id: UUID, name: str) -> KnowledgeBaseSummary: ...

    async def resolve_scope(
        self, workspace_id: UUID, requested_ids: tuple[UUID, ...]
    ) -> tuple[UUID, ...]: ...
