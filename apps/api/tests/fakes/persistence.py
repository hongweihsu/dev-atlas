from types import TracebackType

from devatlas.application.ports.persistence import NewDocumentRecord


class FakeDocumentIngestionRepository:
    def __init__(self) -> None:
        self.staged: list[NewDocumentRecord] = []

    async def add(self, document: NewDocumentRecord) -> None:
        self.staged.append(document)


class FakeIngestionUnitOfWork:
    def __init__(
        self,
        committed_documents: list[NewDocumentRecord],
        *,
        fail_on_commit: bool = False,
    ) -> None:
        self._committed_documents = committed_documents
        self._fail_on_commit = fail_on_commit
        self._committed = False
        self.documents = FakeDocumentIngestionRepository()
        self.commit_calls = 0
        self.rollback_calls = 0

    async def __aenter__(self) -> "FakeIngestionUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None or not self._committed:
            await self.rollback()

    async def commit(self) -> None:
        self.commit_calls += 1
        if self._fail_on_commit:
            raise RuntimeError("database commit failed")
        self._committed_documents.extend(self.documents.staged)
        self.documents.staged.clear()
        self._committed = True

    async def rollback(self) -> None:
        self.rollback_calls += 1
        self.documents.staged.clear()


class FakeIngestionUnitOfWorkFactory:
    def __init__(self, *, fail_on_commit: bool = False) -> None:
        self.committed_documents: list[NewDocumentRecord] = []
        self.fail_on_commit = fail_on_commit
        self.created: list[FakeIngestionUnitOfWork] = []

    def __call__(self) -> FakeIngestionUnitOfWork:
        unit_of_work = FakeIngestionUnitOfWork(
            self.committed_documents,
            fail_on_commit=self.fail_on_commit,
        )
        self.created.append(unit_of_work)
        return unit_of_work
