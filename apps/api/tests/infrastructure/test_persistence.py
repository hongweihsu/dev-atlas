from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from retrieval_works.application.ports.persistence import (
    NewChunkRecord,
    NewDocumentRecord,
    NewDocumentVersionRecord,
)
from retrieval_works.core.tenancy import LEGACY_WORKSPACE_ID
from retrieval_works.infrastructure.models import Document
from retrieval_works.infrastructure.persistence import (
    SqlAlchemyDocumentIngestionRepository,
    SqlAlchemyIngestionUnitOfWork,
)


def make_record() -> NewDocumentRecord:
    text = "A small document"
    return NewDocumentRecord(
        id=uuid4(),
        title="Architecture notes",
        version=NewDocumentVersionRecord(
            id=uuid4(),
            version_number=1,
            source_filename="notes.txt",
            media_type="text/plain",
            content_checksum="a" * 64,
            normalized_text=text,
            byte_size=len(text.encode()),
            character_count=len(text),
            is_active=True,
            embedding_model="fake-embedding",
            embedding_dimension=1536,
            chunks=(
                NewChunkRecord(
                    id=uuid4(),
                    ordinal=0,
                    text=text,
                    start_offset=0,
                    end_offset=len(text),
                    embedding=(0.0,) * 1536,
                ),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_repository_maps_complete_document_aggregate() -> None:
    session = MagicMock(spec=AsyncSession)
    knowledge_base_id = uuid4()
    session.scalar = AsyncMock(return_value=knowledge_base_id)
    duplicate_result = MagicMock()
    duplicate_result.first.return_value = None
    session.execute = AsyncMock(side_effect=[MagicMock(), duplicate_result])
    repository = SqlAlchemyDocumentIngestionRepository(session)
    record = make_record()

    await repository.add(LEGACY_WORKSPACE_ID, record)

    document = session.add.call_args.args[0]
    assert isinstance(document, Document)
    assert document.id == record.id
    assert document.workspace_id == LEGACY_WORKSPACE_ID
    assert document.knowledge_base_id == knowledge_base_id
    assert document.title == record.title
    assert len(document.versions) == 1
    assert document.versions[0].id == record.version.id
    assert document.versions[0].document is document
    assert len(document.versions[0].chunks) == 1
    assert document.versions[0].chunks[0].document_version is document.versions[0]
    assert document.versions[0].chunks[0].embedding == [0.0] * 1536


@pytest.mark.asyncio
async def test_unit_of_work_commits_and_closes_session() -> None:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    unit_of_work = SqlAlchemyIngestionUnitOfWork(lambda: session)

    async with unit_of_work:
        await unit_of_work.commit()

    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_unit_of_work_rolls_back_uncommitted_work() -> None:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    unit_of_work = SqlAlchemyIngestionUnitOfWork(lambda: session)

    async with unit_of_work:
        assert unit_of_work.documents is not None

    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_unit_of_work_rolls_back_when_commit_fails() -> None:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    unit_of_work = SqlAlchemyIngestionUnitOfWork(lambda: session)

    with pytest.raises(RuntimeError, match="commit failed"):
        async with unit_of_work:
            await unit_of_work.commit()

    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()
