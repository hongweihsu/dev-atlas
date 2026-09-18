import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from arq import Retry, cron
from arq.connections import RedisSettings
from openai import AsyncOpenAI
from sqlalchemy import select

from devatlas.application.ingest_document import (
    IngestNewDocument,
    IngestNewDocumentCommand,
)
from devatlas.application.ports.document_extraction import (
    DocumentExtractionUnavailableError,
)
from devatlas.application.ports.embedding import EmbeddingProviderUnavailableError
from devatlas.application.ports.persistence import DuplicateDocumentContentError
from devatlas.core.config import get_settings
from devatlas.domain.document_ingestion import DocumentValidationError
from devatlas.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from devatlas.infrastructure.embedding import OpenAIEmbeddingProvider
from devatlas.infrastructure.extraction import OpenAIMultimodalDocumentExtractor
from devatlas.infrastructure.maintenance import SqlAlchemyRetentionCleaner
from devatlas.infrastructure.models import (
    DocumentVersion,
    IngestionJob,
    IngestionOutboxEvent,
)
from devatlas.infrastructure.persistence import SqlAlchemyIngestionUnitOfWorkFactory
from devatlas.infrastructure.queue import ArqIngestionQueue

MAX_JOB_ATTEMPTS = 3


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    if settings.openai_api_key is None:
        raise RuntimeError("OPENAI_API_KEY is required by the ingestion worker")
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
    provider = OpenAIEmbeddingProvider(
        client, model=settings.embedding_model, dimension=settings.embedding_dimension
    )
    ctx.update(
        engine=engine,
        session_factory=session_factory,
        client=client,
        ingestion=IngestNewDocument(
            embedding_provider=provider,
            document_extractor=OpenAIMultimodalDocumentExtractor(
                client, model=settings.answer_model
            ),
            unit_of_work_factory=SqlAlchemyIngestionUnitOfWorkFactory(session_factory),
            expected_embedding_dimension=settings.embedding_dimension,
        ),
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["client"].close()
    await ctx["engine"].dispose()


async def process_ingestion_job(ctx: dict[str, Any], job_id: str) -> None:
    session_factory = ctx["session_factory"]
    identifier = UUID(job_id)
    async with session_factory() as session:
        job = await session.scalar(
            select(IngestionJob).where(IngestionJob.id == identifier).with_for_update()
        )
        if job is None or job.status in {"succeeded", "failed"}:
            return
        job.status = "processing"
        job.attempt_count += 1
        job.started_at = datetime.now(UTC)
        await session.commit()
        command = IngestNewDocumentCommand(
            title=job.title,
            source_filename=job.source_filename,
            media_type=job.media_type,
            content=job.content,
            knowledge_base_id=job.knowledge_base_id,
            document_id=identifier,
        )
        workspace_id = job.workspace_id
        attempt = job.attempt_count

    try:
        result = await ctx["ingestion"].execute(workspace_id, command)
    except EmbeddingProviderUnavailableError as error:
        await _record_failure(
            ctx,
            identifier,
            "embedding_unavailable",
            str(error),
            final=attempt >= MAX_JOB_ATTEMPTS,
        )
        if attempt < MAX_JOB_ATTEMPTS:
            raise Retry(defer=2**attempt) from error
    except DocumentExtractionUnavailableError as error:
        await _record_failure(
            ctx,
            identifier,
            "document_extraction_unavailable",
            str(error),
            final=attempt >= MAX_JOB_ATTEMPTS,
        )
        if attempt < MAX_JOB_ATTEMPTS:
            raise Retry(defer=2**attempt) from error
    except DuplicateDocumentContentError as error:
        if error.document_id == identifier:
            async with session_factory() as session:
                version_id = await session.scalar(
                    select(DocumentVersion.id).where(
                        DocumentVersion.document_id == identifier,
                        DocumentVersion.is_active.is_(True),
                    )
                )
                job = await session.get(IngestionJob, identifier)
                if job is not None and version_id is not None:
                    job.status = "succeeded"
                    job.document_id = identifier
                    job.version_id = version_id
                    job.finished_at = datetime.now(UTC)
                    job.content = b"processed"
                    await session.commit()
                    return
        await _record_failure(
            ctx,
            identifier,
            "duplicate_document_content",
            str(error),
            final=True,
        )
    except DocumentValidationError as error:
        await _record_failure(ctx, identifier, str(error.code), str(error), final=True)
    except Exception as error:
        await _record_failure(
            ctx, identifier, "ingestion_failed", str(error), final=True
        )
    else:
        async with session_factory() as session:
            job = await session.get(IngestionJob, identifier)
            if job is not None:
                job.status = "succeeded"
                job.document_id = result.document_id
                job.version_id = result.version_id
                job.finished_at = datetime.now(UTC)
                job.content = b"processed"
                await session.commit()


async def cleanup_expired_operational_data(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    result = await SqlAlchemyRetentionCleaner(ctx["session_factory"]).run(
        terminal_job_retention_days=settings.terminal_job_retention_days,
        accepted_invitation_retention_days=(
            settings.accepted_invitation_retention_days
        ),
    )
    logging.getLogger("devatlas.maintenance").info(
        "retention_cleanup_completed",
        extra={
            "ingestion_jobs_deleted": result.ingestion_jobs_deleted,
            "invitations_deleted": result.invitations_deleted,
        },
    )


async def dispatch_ingestion_outbox(ctx: dict[str, Any]) -> None:
    queue = ArqIngestionQueue(ctx["redis"])
    async with ctx["session_factory"]() as session, session.begin():
        events = list(
            await session.scalars(
                select(IngestionOutboxEvent)
                .where(IngestionOutboxEvent.published_at.is_(None))
                .order_by(IngestionOutboxEvent.created_at)
                .limit(50)
                .with_for_update(skip_locked=True)
            )
        )
        for event in events:
            try:
                await queue.enqueue(event.job_id)
            except Exception as error:
                event.attempt_count += 1
                event.last_error = str(error)[:500]
            else:
                event.attempt_count += 1
                event.last_error = None
                event.published_at = datetime.now(UTC)


async def _record_failure(
    ctx: dict[str, Any],
    job_id: UUID,
    code: str,
    message: str,
    *,
    final: bool,
) -> None:
    async with ctx["session_factory"]() as session:
        job = await session.get(IngestionJob, job_id)
        if job is not None:
            job.status = "failed" if final else "queued"
            job.error_code = code
            job.error_message = message[:2000]
            job.finished_at = datetime.now(UTC) if final else None
            if final:
                job.content = b"processed"
            await session.commit()


class WorkerSettings:
    functions = [process_ingestion_job, dispatch_ingestion_outbox]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = MAX_JOB_ATTEMPTS
    cron_jobs = [
        cron(cleanup_expired_operational_data, hour=3, minute=30),
        cron(
            dispatch_ingestion_outbox,
            second={0, 10, 20, 30, 40, 50},
            run_at_startup=True,
        ),
    ]
