from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from devatlas.application.manage_ingestion_jobs import (
    InvalidIdempotencyKeyError,
    ManageIngestionJobs,
)
from devatlas.application.ports.ingestion_jobs import IngestionJobSnapshot


@pytest.mark.asyncio
async def test_submit_persists_before_enqueue_and_reuses_repository_identity() -> None:
    repository = AsyncMock()
    queue = AsyncMock()
    job_id = uuid4()
    repository.create_or_get.return_value = IngestionJobSnapshot(
        id=job_id,
        status="queued",
        attempt_count=0,
        document_id=None,
        version_id=None,
        error_code=None,
        error_message=None,
        created_at=datetime.now(UTC),
        started_at=None,
        finished_at=None,
    )
    service = ManageIngestionJobs(repository=repository, queue=queue)

    result = await service.submit(
        workspace_id=uuid4(),
        knowledge_base_id=uuid4(),
        idempotency_key="upload-42",
        title="Notes",
        source_filename="notes.txt",
        media_type="text/plain",
        content=b"bounded content",
    )

    assert result.id == job_id
    queue.enqueue.assert_awaited_once_with(job_id)
    assert repository.create_or_get.await_count == 1


@pytest.mark.asyncio
async def test_completed_idempotent_submission_is_not_enqueued_again() -> None:
    repository = AsyncMock()
    queue = AsyncMock()
    repository.create_or_get.return_value = IngestionJobSnapshot(
        id=uuid4(),
        status="succeeded",
        attempt_count=1,
        document_id=uuid4(),
        version_id=uuid4(),
        error_code=None,
        error_message=None,
        created_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    service = ManageIngestionJobs(repository=repository, queue=queue)

    await service.submit(
        workspace_id=uuid4(),
        knowledge_base_id=uuid4(),
        idempotency_key="same-key",
        title="Notes",
        source_filename="notes.txt",
        media_type="text/plain",
        content=b"content",
    )

    queue.enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_blank_idempotency_key_is_rejected_before_persistence() -> None:
    repository = AsyncMock()
    service = ManageIngestionJobs(repository=repository, queue=AsyncMock())

    with pytest.raises(InvalidIdempotencyKeyError):
        await service.submit(
            workspace_id=uuid4(),
            knowledge_base_id=uuid4(),
            idempotency_key=" ",
            title="Notes",
            source_filename="notes.txt",
            media_type="text/plain",
            content=b"content",
        )

    repository.create_or_get.assert_not_awaited()
