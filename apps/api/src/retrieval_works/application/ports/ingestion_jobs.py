from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

type IngestionJobStatus = Literal["queued", "processing", "succeeded", "failed"]


@dataclass(frozen=True, slots=True)
class NewIngestionJob:
    id: UUID
    workspace_id: UUID
    knowledge_base_id: UUID
    idempotency_key: str
    title: str
    source_filename: str
    media_type: str
    content: bytes
    content_checksum: str


@dataclass(frozen=True, slots=True)
class IngestionJobSnapshot:
    id: UUID
    status: IngestionJobStatus
    attempt_count: int
    document_id: UUID | None
    version_id: UUID | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class IngestionJobRepository(Protocol):
    async def create_or_get(self, job: NewIngestionJob) -> IngestionJobSnapshot: ...

    async def get(self, workspace_id: UUID, job_id: UUID) -> IngestionJobSnapshot: ...


class IngestionQueue(Protocol):
    async def enqueue(self, job_id: UUID) -> None: ...


class IngestionJobNotFoundError(LookupError):
    pass


class IngestionQueueUnavailableError(RuntimeError):
    pass


class IdempotencyConflictError(ValueError):
    pass
