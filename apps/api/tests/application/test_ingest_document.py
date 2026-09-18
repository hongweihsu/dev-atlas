from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from retrieval_works.application.ingest_document import (
    IngestNewDocument,
    IngestNewDocumentCommand,
)
from retrieval_works.application.ports.embedding import EmbeddingBatchError
from retrieval_works.application.ports.persistence import (
    DocumentArchivedError,
    DocumentNotFoundError,
    DuplicateDocumentContentError,
    IngestionUnitOfWorkFactory,
)
from retrieval_works.domain.document_ingestion import PreparedTextDocument
from retrieval_works.domain.text_processing import content_checksum
from tests.fakes import (
    DeterministicEmbeddingProvider,
    FakeIngestionUnitOfWorkFactory,
)

WORKSPACE_ID = UUID(int=999)


def accepts_unit_of_work_factory(
    factory: IngestionUnitOfWorkFactory,
) -> IngestionUnitOfWorkFactory:
    """Compile-time assertion that the fake satisfies the application protocol."""
    return factory


def make_command(*, title: str = "Retrieval Works Notes") -> IngestNewDocumentCommand:
    return IngestNewDocumentCommand(
        title=title,
        source_filename="notes.txt",
        media_type="text/plain",
        content=("A" * 1100).encode(),
    )


@pytest.mark.asyncio
async def test_ingest_new_document_commits_complete_version_one() -> None:
    factory = FakeIngestionUnitOfWorkFactory()
    use_case = IngestNewDocument(
        embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        unit_of_work_factory=accepts_unit_of_work_factory(factory),
        expected_embedding_dimension=8,
    )

    result = await use_case.execute(
        WORKSPACE_ID, make_command(title="  Retrieval Works Notes  ")
    )

    assert result.chunk_count == 2
    assert result.version_number == 1
    assert len(factory.committed_documents) == 1
    assert factory.created[0].commit_calls == 1
    assert factory.created[0].rollback_calls == 0

    document = factory.committed_documents[0]
    assert document.id == result.document_id
    assert document.title == "Retrieval Works Notes"
    assert document.version.id == result.version_id
    assert document.version.version_number == 1
    assert document.version.is_active is True
    assert document.version.content_checksum == result.checksum
    assert document.version.embedding_model == "deterministic-test-v1"
    assert document.version.embedding_dimension == 8
    assert [chunk.ordinal for chunk in document.version.chunks] == [0, 1]
    assert all(len(chunk.embedding) == 8 for chunk in document.version.chunks)


@pytest.mark.asyncio
async def test_ingest_new_document_uses_supplied_document_id() -> None:
    factory = FakeIngestionUnitOfWorkFactory()
    use_case = IngestNewDocument(
        embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        unit_of_work_factory=factory,
        expected_embedding_dimension=8,
    )
    intended_document_id = uuid4()
    command = make_command()

    result = await use_case.execute(
        WORKSPACE_ID,
        IngestNewDocumentCommand(
            title=command.title,
            source_filename=command.source_filename,
            media_type=command.media_type,
            content=command.content,
            document_id=intended_document_id,
        ),
    )

    assert result.document_id == intended_document_id
    assert factory.committed_documents[0].id == intended_document_id


@pytest.mark.asyncio
async def test_ingestion_uses_injected_document_extractor() -> None:
    class Extractor:
        calls = 0

        async def prepare(
            self, *, content: bytes, source_filename: str, media_type: str
        ) -> PreparedTextDocument:
            self.calls += 1
            text = "Extracted table: DA-42 is ready."
            return PreparedTextDocument(
                source_filename=source_filename,
                media_type=media_type,
                normalized_text=text,
                content_checksum=content_checksum(text),
                byte_size=len(content),
                character_count=len(text),
            )

    extractor = Extractor()
    factory = FakeIngestionUnitOfWorkFactory()
    use_case = IngestNewDocument(
        embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        document_extractor=extractor,
        unit_of_work_factory=factory,
        expected_embedding_dimension=8,
    )

    await use_case.execute(WORKSPACE_ID, make_command())

    assert extractor.calls == 1
    assert (
        factory.committed_documents[0].version.normalized_text
        == "Extracted table: DA-42 is ready."
    )


@pytest.mark.asyncio
async def test_ingest_new_document_rolls_back_failed_commit() -> None:
    factory = FakeIngestionUnitOfWorkFactory(fail_on_commit=True)
    use_case = IngestNewDocument(
        embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        unit_of_work_factory=factory,
        expected_embedding_dimension=8,
    )

    with pytest.raises(RuntimeError, match="database commit failed"):
        await use_case.execute(WORKSPACE_ID, make_command())

    assert factory.committed_documents == []
    assert factory.created[0].commit_calls == 1
    assert factory.created[0].rollback_calls == 1
    assert factory.created[0].documents.staged == []


class WrongCountEmbeddingProvider(DeterministicEmbeddingProvider):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        embeddings = await super().embed(texts)
        return embeddings[:-1]


@pytest.mark.asyncio
async def test_bad_embeddings_do_not_open_transaction() -> None:
    factory = FakeIngestionUnitOfWorkFactory()
    use_case = IngestNewDocument(
        embedding_provider=WrongCountEmbeddingProvider(dimension=8),
        unit_of_work_factory=factory,
        expected_embedding_dimension=8,
    )

    with pytest.raises(EmbeddingBatchError, match="expected 2 embeddings"):
        await use_case.execute(WORKSPACE_ID, make_command())

    assert factory.created == []
    assert factory.committed_documents == []


@pytest.mark.asyncio
@pytest.mark.parametrize("title", ["", "   ", "a" * 256])
async def test_ingest_new_document_rejects_invalid_title_before_external_work(
    title: str,
) -> None:
    provider = DeterministicEmbeddingProvider(dimension=8)
    factory = FakeIngestionUnitOfWorkFactory()
    use_case = IngestNewDocument(
        embedding_provider=provider,
        unit_of_work_factory=factory,
        expected_embedding_dimension=8,
    )

    with pytest.raises(ValueError, match="title must"):
        await use_case.execute(WORKSPACE_ID, make_command(title=title))

    assert factory.created == []


def test_ingest_new_document_rejects_provider_dimension_mismatch() -> None:
    with pytest.raises(
        ValueError,
        match="provider dimension 8 does not match configured dimension 1536",
    ):
        IngestNewDocument(
            embedding_provider=DeterministicEmbeddingProvider(dimension=8),
            unit_of_work_factory=FakeIngestionUnitOfWorkFactory(),
        )


@pytest.mark.asyncio
async def test_ingest_changed_content_creates_next_document_version() -> None:
    factory = FakeIngestionUnitOfWorkFactory()
    use_case = IngestNewDocument(
        embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        unit_of_work_factory=factory,
        expected_embedding_dimension=8,
    )
    original = await use_case.execute(WORKSPACE_ID, make_command())

    result = await use_case.execute_version(
        WORKSPACE_ID,
        original.document_id,
        IngestNewDocumentCommand(
            title="",
            source_filename="notes-v2.txt",
            media_type="text/plain",
            content=b"changed content",
        ),
    )

    assert result.document_id == original.document_id
    assert result.version_number == 2
    assert factory.committed_documents[-1].version.version_number == 2


@pytest.mark.asyncio
async def test_ingest_duplicate_content_is_rejected() -> None:
    factory = FakeIngestionUnitOfWorkFactory()
    use_case = IngestNewDocument(
        embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        unit_of_work_factory=factory,
        expected_embedding_dimension=8,
    )
    original = await use_case.execute(WORKSPACE_ID, make_command())

    with pytest.raises(DuplicateDocumentContentError, match="same content"):
        await use_case.execute_version(
            WORKSPACE_ID, original.document_id, make_command()
        )


@pytest.mark.asyncio
async def test_new_document_rejects_content_that_already_exists_globally() -> None:
    factory = FakeIngestionUnitOfWorkFactory()
    use_case = IngestNewDocument(
        embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        unit_of_work_factory=factory,
        expected_embedding_dimension=8,
    )
    original = await use_case.execute(WORKSPACE_ID, make_command(title="First title"))

    with pytest.raises(DuplicateDocumentContentError) as caught:
        await use_case.execute(WORKSPACE_ID, make_command(title="Different title"))

    assert caught.value.document_id == original.document_id
    assert len(factory.committed_documents) == 1


@pytest.mark.asyncio
async def test_ingest_version_rejects_unknown_document() -> None:
    use_case = IngestNewDocument(
        embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        unit_of_work_factory=FakeIngestionUnitOfWorkFactory(),
        expected_embedding_dimension=8,
    )

    with pytest.raises(DocumentNotFoundError, match="was not found"):
        await use_case.execute_version(WORKSPACE_ID, uuid4(), make_command())


class NeverCalledEmbeddingProvider(DeterministicEmbeddingProvider):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise AssertionError(f"embedding must not be called for {list(texts)}")


@pytest.mark.asyncio
async def test_archived_document_rejects_version_before_embedding() -> None:
    factory = FakeIngestionUnitOfWorkFactory()
    creator = IngestNewDocument(
        embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        unit_of_work_factory=factory,
        expected_embedding_dimension=8,
    )
    original = await creator.execute(WORKSPACE_ID, make_command())
    factory.archived_document_ids.add(original.document_id)
    updater = IngestNewDocument(
        embedding_provider=NeverCalledEmbeddingProvider(dimension=8),
        unit_of_work_factory=factory,
        expected_embedding_dimension=8,
    )

    with pytest.raises(DocumentArchivedError, match="must be restored"):
        await updater.execute_version(
            WORKSPACE_ID, original.document_id, make_command()
        )
