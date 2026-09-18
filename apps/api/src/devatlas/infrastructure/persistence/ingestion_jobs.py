from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from devatlas.application.ports.ingestion_jobs import (
    IdempotencyConflictError,
    IngestionJobNotFoundError,
    IngestionJobSnapshot,
    NewIngestionJob,
)
from devatlas.infrastructure.models import IngestionJob, IngestionOutboxEvent
from devatlas.infrastructure.persistence.unit_of_work import SessionFactory


class SqlAlchemyIngestionJobRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def create_or_get(self, job: NewIngestionJob) -> IngestionJobSnapshot:
        model = IngestionJob(
            id=job.id,
            workspace_id=job.workspace_id,
            knowledge_base_id=job.knowledge_base_id,
            idempotency_key=job.idempotency_key,
            status="queued",
            attempt_count=0,
            title=job.title,
            source_filename=job.source_filename,
            media_type=job.media_type,
            content=job.content,
            content_checksum=job.content_checksum,
        )
        try:
            async with self._session_factory() as session:
                session.add(model)
                session.add(IngestionOutboxEvent(job_id=job.id))
                await session.commit()
                await session.refresh(model)
        except IntegrityError as error:
            async with self._session_factory() as session:
                existing = await session.scalar(
                    select(IngestionJob).where(
                        IngestionJob.workspace_id == job.workspace_id,
                        IngestionJob.idempotency_key == job.idempotency_key,
                    )
                )
            if existing is None:
                raise
            if (
                existing.knowledge_base_id != job.knowledge_base_id
                or existing.title != job.title
                or existing.source_filename != job.source_filename
                or existing.media_type != job.media_type
                or existing.content_checksum != job.content_checksum
            ):
                raise IdempotencyConflictError(
                    "Idempotency-Key was already used for a different upload"
                ) from error
            model = existing
        return self._snapshot(model)

    async def get(self, workspace_id: UUID, job_id: UUID) -> IngestionJobSnapshot:
        async with self._session_factory() as session:
            model = await session.scalar(
                select(IngestionJob).where(
                    IngestionJob.id == job_id,
                    IngestionJob.workspace_id == workspace_id,
                )
            )
        if model is None:
            raise IngestionJobNotFoundError(f"ingestion job {job_id} was not found")
        return self._snapshot(model)

    @staticmethod
    def _snapshot(model: IngestionJob) -> IngestionJobSnapshot:
        return IngestionJobSnapshot(
            id=model.id,
            status=model.status,  # type: ignore[arg-type]
            attempt_count=model.attempt_count,
            document_id=model.document_id,
            version_id=model.version_id,
            error_code=model.error_code,
            error_message=model.error_message,
            created_at=model.created_at,
            started_at=model.started_at,
            finished_at=model.finished_at,
        )
