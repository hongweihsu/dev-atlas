from types import TracebackType
from uuid import UUID

from devatlas.application.ports.persistence import (
    DocumentArchivedError,
    DocumentNotFoundError,
    DuplicateDocumentContentError,
    NewDocumentRecord,
    NewDocumentVersionRecord,
)


class FakeDocumentIngestionRepository:
    def __init__(
        self,
        committed_documents: list[NewDocumentRecord],
        archived_document_ids: set[UUID],
    ) -> None:
        self._committed_documents = committed_documents
        self._archived_document_ids = archived_document_ids
        self.staged: list[NewDocumentRecord] = []

    async def add(self, workspace_id: UUID, document: NewDocumentRecord) -> None:
        del workspace_id
        duplicate = next(
            (
                item
                for item in self._committed_documents
                if item.version.content_checksum == document.version.content_checksum
            ),
            None,
        )
        if duplicate is not None:
            raise DuplicateDocumentContentError(
                "this content already exists in another document",
                document_id=duplicate.id,
            )
        self.staged.append(document)

    async def add_version(
        self,
        workspace_id: UUID,
        document_id: UUID,
        version: NewDocumentVersionRecord,
    ) -> int:
        del workspace_id
        versions = [
            item for item in self._committed_documents if item.id == document_id
        ]
        if not versions:
            raise DocumentNotFoundError(f"document {document_id} was not found")
        if any(
            item.version.content_checksum == version.content_checksum
            for item in versions
        ):
            raise DuplicateDocumentContentError(
                "this document already has a version with the same content"
            )
        next_number = max(item.version.version_number for item in versions) + 1
        updated_version = NewDocumentVersionRecord(
            id=version.id,
            version_number=next_number,
            source_filename=version.source_filename,
            media_type=version.media_type,
            content_checksum=version.content_checksum,
            normalized_text=version.normalized_text,
            byte_size=version.byte_size,
            character_count=version.character_count,
            is_active=True,
            embedding_model=version.embedding_model,
            embedding_dimension=version.embedding_dimension,
            chunks=version.chunks,
        )
        self.staged.append(
            NewDocumentRecord(
                id=document_id,
                title=versions[0].title,
                version=updated_version,
            )
        )
        return next_number

    async def ensure_version_target(
        self, workspace_id: UUID, document_id: UUID
    ) -> None:
        del workspace_id
        if not any(item.id == document_id for item in self._committed_documents):
            raise DocumentNotFoundError(f"document {document_id} was not found")
        if document_id in self._archived_document_ids:
            raise DocumentArchivedError(
                f"document {document_id} must be restored before adding a version"
            )


class FakeIngestionUnitOfWork:
    def __init__(
        self,
        committed_documents: list[NewDocumentRecord],
        archived_document_ids: set[UUID],
        *,
        fail_on_commit: bool = False,
    ) -> None:
        self._committed_documents = committed_documents
        self._fail_on_commit = fail_on_commit
        self._committed = False
        self.documents = FakeDocumentIngestionRepository(
            committed_documents, archived_document_ids
        )
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
        self.archived_document_ids: set[UUID] = set()
        self.fail_on_commit = fail_on_commit
        self.created: list[FakeIngestionUnitOfWork] = []

    def __call__(self) -> FakeIngestionUnitOfWork:
        unit_of_work = FakeIngestionUnitOfWork(
            self.committed_documents,
            self.archived_document_ids,
            fail_on_commit=self.fail_on_commit,
        )
        self.created.append(unit_of_work)
        return unit_of_work
