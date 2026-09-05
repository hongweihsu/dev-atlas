import os

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import selectinload

from devatlas.application.ingest_document import (
    IngestNewDocument,
    IngestNewDocumentCommand,
)
from devatlas.infrastructure.database import create_session_factory
from devatlas.infrastructure.models import Document, DocumentVersion
from devatlas.infrastructure.persistence import (
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
