import os
from hashlib import sha256
from typing import Any, cast
from uuid import uuid4

import pytest
from arq.connections import ArqRedis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine

from retrieval_works.application.ports.ingestion_jobs import NewIngestionJob
from retrieval_works.infrastructure.database import create_session_factory
from retrieval_works.infrastructure.models import (
    IngestionJob,
    IngestionOutboxEvent,
    KnowledgeBase,
)
from retrieval_works.infrastructure.persistence import SqlAlchemyIngestionJobRepository
from retrieval_works.worker import dispatch_ingestion_outbox

TEST_DATABASE_URL = os.getenv("RETRIEVAL_WORKS_TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        TEST_DATABASE_URL is None,
        reason="RETRIEVAL_WORKS_TEST_DATABASE_URL is not configured",
    ),
]


class FakeRedis:
    def __init__(self) -> None:
        self.job_ids: list[str] = []

    async def enqueue_job(self, _function: str, job_id: str, **_kwargs: Any) -> object:
        self.job_ids.append(job_id)
        return object()


@pytest.mark.asyncio
async def test_job_and_outbox_commit_atomically_then_dispatch() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)
    job_id = uuid4()
    redis = FakeRedis()
    try:
        async with session_factory() as session:
            knowledge_base = await session.scalar(select(KnowledgeBase).limit(1))
        assert knowledge_base is not None
        content = b"transactional outbox integration"
        repository = SqlAlchemyIngestionJobRepository(session_factory)
        await repository.create_or_get(
            NewIngestionJob(
                id=job_id,
                workspace_id=knowledge_base.workspace_id,
                knowledge_base_id=knowledge_base.id,
                idempotency_key=str(uuid4()),
                title="Outbox integration",
                source_filename="outbox.txt",
                media_type="text/plain",
                content=content,
                content_checksum=sha256(content).hexdigest(),
            )
        )

        await dispatch_ingestion_outbox(
            {
                "session_factory": session_factory,
                "redis": cast(ArqRedis, cast(Any, redis)),
            }
        )

        async with session_factory() as session:
            event = await session.scalar(
                select(IngestionOutboxEvent).where(
                    IngestionOutboxEvent.job_id == job_id
                )
            )
        assert redis.job_ids == [str(job_id)]
        assert event is not None and event.published_at is not None
        assert event.attempt_count == 1
    finally:
        async with session_factory.begin() as session:
            await session.execute(delete(IngestionJob).where(IngestionJob.id == job_id))
        await engine.dispose()
