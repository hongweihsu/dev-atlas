from collections.abc import Callable
from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession

from retrieval_works.application.ports.persistence import DocumentIngestionRepository
from retrieval_works.infrastructure.persistence.repository import (
    SqlAlchemyDocumentIngestionRepository,
)

SessionFactory = Callable[[], AsyncSession]


class SqlAlchemyIngestionUnitOfWork:
    """Own one SQLAlchemy session and transaction for an ingestion attempt."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._documents: DocumentIngestionRepository | None = None
        self._committed = False

    @property
    def documents(self) -> DocumentIngestionRepository:
        if self._documents is None:
            raise RuntimeError("Unit of Work has not been entered")
        return self._documents

    async def __aenter__(self) -> "SqlAlchemyIngestionUnitOfWork":
        if self._session is not None:
            raise RuntimeError("Unit of Work cannot be entered more than once")
        self._session = self._session_factory()
        self._documents = SqlAlchemyDocumentIngestionRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        try:
            if exc_type is not None or not self._committed:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None
            self._documents = None

    async def commit(self) -> None:
        session = self._require_session()
        await session.commit()
        self._committed = True

    async def rollback(self) -> None:
        session = self._require_session()
        await session.rollback()

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return self._session


class SqlAlchemyIngestionUnitOfWorkFactory:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def __call__(self) -> SqlAlchemyIngestionUnitOfWork:
        return SqlAlchemyIngestionUnitOfWork(self._session_factory)
