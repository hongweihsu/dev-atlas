from uuid import UUID

from retrieval_works.application.ports.knowledge_bases import (
    InvalidKnowledgeBaseScopeError,
    KnowledgeBaseRepository,
    KnowledgeBaseSummary,
)


class InvalidKnowledgeBaseNameError(ValueError):
    """Raised when a knowledge-base name violates the bounded contract."""


class ManageKnowledgeBases:
    def __init__(self, repository: KnowledgeBaseRepository) -> None:
        self._repository = repository

    async def list(self, workspace_id: UUID) -> list[KnowledgeBaseSummary]:
        return await self._repository.list(workspace_id)

    async def create(self, workspace_id: UUID, name: str) -> KnowledgeBaseSummary:
        normalized_name = name.strip()
        if not normalized_name:
            raise InvalidKnowledgeBaseNameError("knowledge base name must not be empty")
        if len(normalized_name) > 255:
            raise InvalidKnowledgeBaseNameError(
                "knowledge base name must not exceed 255 characters"
            )
        return await self._repository.create(workspace_id, normalized_name)

    async def resolve_scope(
        self, workspace_id: UUID, requested_ids: tuple[UUID, ...]
    ) -> tuple[UUID, ...]:
        resolved = await self._repository.resolve_scope(workspace_id, requested_ids)
        if requested_ids and len(resolved) != len(set(requested_ids)):
            raise InvalidKnowledgeBaseScopeError(
                "one or more knowledge bases are unavailable in this workspace"
            )
        if not resolved:
            raise InvalidKnowledgeBaseScopeError(
                "at least one knowledge base must be selected"
            )
        return resolved
