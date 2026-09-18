from hashlib import sha256
from uuid import UUID, uuid4

from devatlas.application.ports.ingestion_jobs import (
    IngestionJobRepository,
    IngestionJobSnapshot,
    NewIngestionJob,
)


class InvalidIdempotencyKeyError(ValueError):
    pass


class ManageIngestionJobs:
    def __init__(self, *, repository: IngestionJobRepository) -> None:
        self._repository = repository

    async def submit(
        self,
        *,
        workspace_id: UUID,
        knowledge_base_id: UUID,
        idempotency_key: str,
        title: str,
        source_filename: str,
        media_type: str,
        content: bytes,
    ) -> IngestionJobSnapshot:
        key = idempotency_key.strip()
        if not key or len(key) > 255:
            raise InvalidIdempotencyKeyError(
                "Idempotency-Key must contain between 1 and 255 characters"
            )
        snapshot = await self._repository.create_or_get(
            NewIngestionJob(
                id=uuid4(),
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                idempotency_key=key,
                title=title,
                source_filename=source_filename,
                media_type=media_type,
                content=content,
                content_checksum=sha256(content).hexdigest(),
            )
        )
        return snapshot

    async def get(self, workspace_id: UUID, job_id: UUID) -> IngestionJobSnapshot:
        return await self._repository.get(workspace_id, job_id)
