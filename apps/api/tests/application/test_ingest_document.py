from collections.abc import Sequence

import pytest

from devatlas.application.ingest_document import (
    IngestNewDocument,
    IngestNewDocumentCommand,
)
from devatlas.application.ports.embedding import EmbeddingBatchError
from devatlas.application.ports.persistence import IngestionUnitOfWorkFactory
from tests.fakes import (
    DeterministicEmbeddingProvider,
    FakeIngestionUnitOfWorkFactory,
)


def accepts_unit_of_work_factory(
    factory: IngestionUnitOfWorkFactory,
) -> IngestionUnitOfWorkFactory:
    """Compile-time assertion that the fake satisfies the application protocol."""
    return factory


def make_command(*, title: str = "DevAtlas Notes") -> IngestNewDocumentCommand:
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

    result = await use_case.execute(make_command(title="  DevAtlas Notes  "))

    assert result.chunk_count == 2
    assert len(factory.committed_documents) == 1
    assert factory.created[0].commit_calls == 1
    assert factory.created[0].rollback_calls == 0

    document = factory.committed_documents[0]
    assert document.id == result.document_id
    assert document.title == "DevAtlas Notes"
    assert document.version.id == result.version_id
    assert document.version.version_number == 1
    assert document.version.is_active is True
    assert document.version.content_checksum == result.checksum
    assert document.version.embedding_model == "deterministic-test-v1"
    assert document.version.embedding_dimension == 8
    assert [chunk.ordinal for chunk in document.version.chunks] == [0, 1]
    assert all(len(chunk.embedding) == 8 for chunk in document.version.chunks)


@pytest.mark.asyncio
async def test_ingest_new_document_rolls_back_failed_commit() -> None:
    factory = FakeIngestionUnitOfWorkFactory(fail_on_commit=True)
    use_case = IngestNewDocument(
        embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        unit_of_work_factory=factory,
        expected_embedding_dimension=8,
    )

    with pytest.raises(RuntimeError, match="database commit failed"):
        await use_case.execute(make_command())

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
        await use_case.execute(make_command())

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
        await use_case.execute(make_command(title=title))

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
