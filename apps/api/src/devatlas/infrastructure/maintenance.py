from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import and_, delete, or_
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from devatlas.infrastructure.models import IngestionJob, WorkspaceInvitation


@dataclass(frozen=True, slots=True)
class CleanupResult:
    ingestion_jobs_deleted: int
    invitations_deleted: int


class SqlAlchemyRetentionCleaner:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def run(
        self,
        *,
        terminal_job_retention_days: int,
        accepted_invitation_retention_days: int,
        now: datetime | None = None,
    ) -> CleanupResult:
        current_time = now or datetime.now(UTC)
        job_cutoff = current_time - timedelta(days=terminal_job_retention_days)
        invitation_cutoff = current_time - timedelta(
            days=accepted_invitation_retention_days
        )
        async with self._session_factory() as session:
            jobs = await session.execute(
                delete(IngestionJob).where(
                    IngestionJob.status.in_(("succeeded", "failed")),
                    IngestionJob.finished_at < job_cutoff,
                )
            )
            invitations = await session.execute(
                delete(WorkspaceInvitation).where(
                    or_(
                        and_(
                            WorkspaceInvitation.accepted_at.is_(None),
                            WorkspaceInvitation.expires_at < current_time,
                        ),
                        WorkspaceInvitation.accepted_at < invitation_cutoff,
                    )
                )
            )
            await session.commit()
        return CleanupResult(
            ingestion_jobs_deleted=cast(CursorResult[Any], jobs).rowcount,
            invitations_deleted=cast(CursorResult[Any], invitations).rowcount,
        )
