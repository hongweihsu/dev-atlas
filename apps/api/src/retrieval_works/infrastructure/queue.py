from uuid import UUID

from arq.connections import ArqRedis

from retrieval_works.application.ports.ingestion_jobs import (
    IngestionQueueUnavailableError,
)


class ArqIngestionQueue:
    def __init__(self, redis: ArqRedis) -> None:
        self._redis = redis

    async def enqueue(self, job_id: UUID) -> None:
        try:
            await self._redis.enqueue_job(
                "process_ingestion_job", str(job_id), _job_id=str(job_id)
            )
        except Exception as error:
            raise IngestionQueueUnavailableError(
                "ingestion queue is unavailable"
            ) from error
