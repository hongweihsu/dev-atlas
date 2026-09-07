import os

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import selectinload

from devatlas.application.ingest_document import (
    IngestNewDocument,
    IngestNewDocumentCommand,
)
from devatlas.application.search_documents import (
    SearchDocuments,
    SearchDocumentsCommand,
)
from devatlas.infrastructure.database import create_session_factory
from devatlas.infrastructure.models import Document, DocumentVersion
from devatlas.infrastructure.persistence import (
    SqlAlchemyChunkSearchRepository,
    SqlAlchemyIngestionUnitOfWorkFactory,
)
from tests.fakes import DeterministicEmbeddingProvider

TEST_DATABASE_URL = os.getenv("DEVATLAS_TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        TEST_DATABASE_URL is None,
        reason="DEVATLAS_TEST_DATABASE_URL is not configured",
    ),
]


@pytest.mark.asyncio
async def test_ingestion_persists_complete_aggregate_in_postgresql() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)
    use_case = IngestNewDocument(
        embedding_provider=DeterministicEmbeddingProvider(dimension=1536),
        unit_of_work_factory=SqlAlchemyIngestionUnitOfWorkFactory(session_factory),
    )

    try:
        result = await use_case.execute(
            IngestNewDocumentCommand(
                title="PostgreSQL integration test",
                source_filename="integration.txt",
                media_type="text/plain",
                content=("transaction boundaries\n\n" * 80).encode(),
            )
        )

        async with session_factory() as session:
            statement = (
                select(Document)
                .where(Document.id == result.document_id)
                .options(
                    selectinload(Document.versions).selectinload(DocumentVersion.chunks)
                )
            )
            document = (await session.scalars(statement)).one()

            assert document.title == "PostgreSQL integration test"
            assert len(document.versions) == 1
            version = document.versions[0]
            assert version.id == result.version_id
            assert version.is_active is True
            assert len(version.chunks) == result.chunk_count
            assert [chunk.ordinal for chunk in version.chunks] == list(
                range(result.chunk_count)
            )
            assert all(len(chunk.embedding) == 1536 for chunk in version.chunks)
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(Document).where(Document.title == "PostgreSQL integration test")
            )
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_retrieval_ranks_matching_active_chunk_first() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)
    provider = DeterministicEmbeddingProvider(dimension=1536)
    ingestion = IngestNewDocument(
        embedding_provider=provider,
        unit_of_work_factory=SqlAlchemyIngestionUnitOfWorkFactory(session_factory),
    )
    search = SearchDocuments(
        embedding_provider=provider,
        repository=SqlAlchemyChunkSearchRepository(session_factory),
    )
    titles = ["Retrieval transaction fixture", "Retrieval gardening fixture"]

    try:
        transaction_document = await ingestion.execute(
            IngestNewDocumentCommand(
                title=titles[0],
                source_filename="transaction.txt",
                media_type="text/plain",
                content=b"transaction boundaries",
            )
        )
        await ingestion.execute(
            IngestNewDocumentCommand(
                title=titles[1],
                source_filename="gardening.txt",
                media_type="text/plain",
                content=b"gardening tomatoes",
            )
        )

        results = await search.execute(
            SearchDocumentsCommand(query="transaction boundaries", limit=1)
        )

        assert len(results) == 1
        assert results[0].document_id == transaction_document.document_id
        assert results[0].document_title == titles[0]
        assert results[0].version_number == 1
        assert results[0].ordinal == 0
        assert results[0].text == "transaction boundaries"
        assert results[0].similarity == pytest.approx(1.0)

        async with session_factory() as session:
            await session.execute(
                update(DocumentVersion)
                .where(DocumentVersion.id == transaction_document.version_id)
                .values(is_active=False)
            )
            await session.commit()

        active_only_results = await search.execute(
            SearchDocumentsCommand(query="transaction boundaries", limit=1)
        )

        assert active_only_results[0].document_title == titles[1]
    finally:
        async with session_factory() as session:
            await session.execute(delete(Document).where(Document.title.in_(titles)))
            await session.commit()
        await engine.dispose()
