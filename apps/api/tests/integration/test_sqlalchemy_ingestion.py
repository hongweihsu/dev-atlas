import os

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import selectinload

from devatlas.application.ingest_document import (
    IngestNewDocument,
    IngestNewDocumentCommand,
)
from devatlas.application.ports.authentication import AuthenticatedPrincipal
from devatlas.application.ports.persistence import (
    DocumentNotFoundError,
    DuplicateDocumentContentError,
)
from devatlas.application.search_documents import (
    SearchDocuments,
    SearchDocumentsCommand,
)
from devatlas.core.tenancy import LEGACY_WORKSPACE_ID
from devatlas.infrastructure.database import create_session_factory
from devatlas.infrastructure.models import (
    Document,
    DocumentVersion,
    KnowledgeBase,
    User,
    Workspace,
    WorkspaceMembership,
)
from devatlas.infrastructure.persistence import (
    SqlAlchemyChunkSearchRepository,
    SqlAlchemyDocumentLifecycleRepository,
    SqlAlchemyDocumentListRepository,
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyIngestionUnitOfWorkFactory,
    SqlAlchemyWorkspaceAccessRepository,
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
async def test_workspace_bootstrap_is_idempotent_and_creates_default_scope() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)
    repository = SqlAlchemyWorkspaceAccessRepository(session_factory)
    principal = AuthenticatedPrincipal(
        issuer="https://bootstrap.integration.example",
        subject="self-service-user",
    )
    workspace_id = None

    try:
        first = await repository.bootstrap_personal_workspace(principal)
        second = await repository.bootstrap_personal_workspace(principal)
        workspace_id = first.workspace_id

        assert second == first
        assert first.workspace_name == "Personal Workspace"
        assert first.role == "owner"
        async with session_factory() as session:
            knowledge_bases = (
                await session.scalars(
                    select(KnowledgeBase).where(
                        KnowledgeBase.workspace_id == first.workspace_id
                    )
                )
            ).all()
            memberships = (
                await session.scalars(
                    select(WorkspaceMembership).where(
                        WorkspaceMembership.user_id == first.user_id
                    )
                )
            ).all()
        assert [(item.name, item.is_default) for item in knowledge_bases] == [
            ("General", True)
        ]
        assert len(memberships) == 1
    finally:
        if workspace_id is not None:
            async with session_factory.begin() as session:
                await session.execute(
                    delete(KnowledgeBase).where(
                        KnowledgeBase.workspace_id == workspace_id
                    )
                )
                await session.execute(
                    delete(Workspace).where(Workspace.id == workspace_id)
                )
                await session.execute(
                    delete(User).where(
                        User.identity_issuer == principal.issuer,
                        User.identity_subject == principal.subject,
                    )
                )
        await engine.dispose()


@pytest.mark.asyncio
async def test_workspace_invitation_is_email_bound_and_single_use() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)
    repository = SqlAlchemyWorkspaceAccessRepository(session_factory)
    owner = AuthenticatedPrincipal(
        issuer="https://invitations.integration.example",
        subject="workspace-owner",
        email="owner@example.com",
    )
    reader = AuthenticatedPrincipal(
        issuer="https://invitations.integration.example",
        subject="workspace-reader",
        email="reader@example.com",
    )
    workspace_ids = []

    try:
        owner_personal = await repository.bootstrap_personal_workspace(owner)
        reader_personal = await repository.bootstrap_personal_workspace(reader)
        shared = await repository.create_workspace(owner, "Shared research")
        workspace_ids.extend(
            [
                owner_personal.workspace_id,
                reader_personal.workspace_id,
                shared.workspace_id,
            ]
        )
        invitation = await repository.create_invitation(
            shared, "Reader@Example.COM", "viewer"
        )

        with pytest.raises(PermissionError, match="another email"):
            await repository.accept_invitation(owner, invitation.token)

        membership = await repository.accept_invitation(reader, invitation.token)

        assert membership.workspace_id == shared.workspace_id
        assert membership.role == "viewer"
        assert shared.workspace_id in {
            item.workspace_id for item in await repository.list_for_principal(reader)
        }
        members = await repository.list_members(shared)
        assert [(item.email, item.role) for item in members] == [
            ("owner@example.com", "owner"),
            ("reader@example.com", "viewer"),
        ]
        updated = await repository.update_member_role(
            shared, membership.user_id, "editor"
        )
        assert updated.role == "editor"
        with pytest.raises(ValueError, match="already belongs"):
            await repository.create_invitation(shared, reader.email or "", "viewer")
        summaries = await repository.list_invitations(shared)
        assert summaries[0].accepted_at is not None
        with pytest.raises(ValueError, match="cannot be revoked"):
            await repository.revoke_invitation(shared, invitation.invitation_id)
        with pytest.raises(ValueError, match="invalid or expired"):
            await repository.accept_invitation(reader, invitation.token)

        pending = await repository.create_invitation(
            shared, "pending@example.com", "viewer"
        )
        with pytest.raises(ValueError, match="active invitation"):
            await repository.create_invitation(shared, "pending@example.com", "editor")
        await repository.revoke_invitation(shared, pending.invitation_id)
        assert pending.invitation_id not in {
            item.invitation_id for item in await repository.list_invitations(shared)
        }

        await repository.remove_member(shared, membership.user_id)
        assert membership.user_id not in {
            item.user_id for item in await repository.list_members(shared)
        }
        with pytest.raises(ValueError, match="owner membership cannot be removed"):
            await repository.remove_member(shared, shared.user_id)
    finally:
        if workspace_ids:
            async with session_factory.begin() as session:
                await session.execute(
                    delete(KnowledgeBase).where(
                        KnowledgeBase.workspace_id.in_(workspace_ids)
                    )
                )
                await session.execute(
                    delete(Workspace).where(Workspace.id.in_(workspace_ids))
                )
                await session.execute(
                    delete(User).where(User.identity_issuer == owner.issuer)
                )
        await engine.dispose()


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
            LEGACY_WORKSPACE_ID,
            IngestNewDocumentCommand(
                title="PostgreSQL integration test",
                source_filename="integration.txt",
                media_type="text/plain",
                content=("transaction boundaries\n\n" * 80).encode(),
            ),
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
            LEGACY_WORKSPACE_ID,
            IngestNewDocumentCommand(
                title=titles[0],
                source_filename="transaction.txt",
                media_type="text/plain",
                content=b"transaction boundaries",
            ),
        )
        await ingestion.execute(
            LEGACY_WORKSPACE_ID,
            IngestNewDocumentCommand(
                title=titles[1],
                source_filename="gardening.txt",
                media_type="text/plain",
                content=b"gardening tomatoes",
            ),
        )

        results = await search.execute(
            SearchDocumentsCommand(
                query="transaction boundaries",
                workspace_id=LEGACY_WORKSPACE_ID,
                limit=1,
            )
        )

        assert len(results) == 1
        assert results[0].document_id == transaction_document.document_id
        assert results[0].document_title == titles[0]
        assert results[0].version_number == 1
        assert results[0].ordinal == 0
        assert results[0].text == "transaction boundaries"
        assert results[0].score == pytest.approx(1.0)
        assert results[0].scoring_method == "cosine_similarity"

        async with session_factory() as session:
            await session.execute(
                update(DocumentVersion)
                .where(DocumentVersion.id == transaction_document.version_id)
                .values(is_active=False)
            )
            await session.commit()

        active_only_results = await search.execute(
            SearchDocumentsCommand(
                query="transaction boundaries",
                workspace_id=LEGACY_WORKSPACE_ID,
                limit=1,
            )
        )

        assert active_only_results[0].document_title == titles[1]
    finally:
        async with session_factory() as session:
            await session.execute(delete(Document).where(Document.title.in_(titles)))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_reingestion_archives_previous_version_and_rejects_duplicate() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)
    ingestion = IngestNewDocument(
        embedding_provider=DeterministicEmbeddingProvider(dimension=1536),
        unit_of_work_factory=SqlAlchemyIngestionUnitOfWorkFactory(session_factory),
    )
    title = "Document version transition fixture"
    versions_repository = SqlAlchemyDocumentVersionRepository(session_factory)

    try:
        first = await ingestion.execute(
            LEGACY_WORKSPACE_ID,
            IngestNewDocumentCommand(
                title=title,
                source_filename="version-1.txt",
                media_type="text/plain",
                content=b"first version",
            ),
        )
        second = await ingestion.execute_version(
            LEGACY_WORKSPACE_ID,
            first.document_id,
            IngestNewDocumentCommand(
                title="",
                source_filename="version-2.txt",
                media_type="text/plain",
                content=b"second version",
            ),
        )

        assert second.version_number == 2
        async with session_factory() as session:
            versions = (
                await session.scalars(
                    select(DocumentVersion)
                    .where(DocumentVersion.document_id == first.document_id)
                    .order_by(DocumentVersion.version_number)
                )
            ).all()
            assert [version.version_number for version in versions] == [1, 2]
            assert [version.is_active for version in versions] == [False, True]

        summaries = await versions_repository.list_versions(
            LEGACY_WORKSPACE_ID, first.document_id
        )
        assert [summary.version_number for summary in summaries] == [2, 1]
        await versions_repository.activate_version(
            LEGACY_WORKSPACE_ID, first.document_id, first.version_id
        )
        summaries = await versions_repository.list_versions(
            LEGACY_WORKSPACE_ID, first.document_id
        )
        assert [summary.is_active for summary in summaries] == [False, True]

        with pytest.raises(DuplicateDocumentContentError, match="same content"):
            await ingestion.execute_version(
                LEGACY_WORKSPACE_ID,
                first.document_id,
                IngestNewDocumentCommand(
                    title="",
                    source_filename="version-2-again.txt",
                    media_type="text/plain",
                    content=b"second version",
                ),
            )
    finally:
        async with session_factory() as session:
            await session.execute(delete(Document).where(Document.title == title))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_catalog_and_workspace_duplicate_protection() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)
    ingestion = IngestNewDocument(
        embedding_provider=DeterministicEmbeddingProvider(dimension=1536),
        unit_of_work_factory=SqlAlchemyIngestionUnitOfWorkFactory(session_factory),
    )
    document_list = SqlAlchemyDocumentListRepository(session_factory)
    titles = ["Catalog integration fixture", "Catalog duplicate fixture"]
    content = b"catalog integration content unique to this test"

    try:
        created = await ingestion.execute(
            LEGACY_WORKSPACE_ID,
            IngestNewDocumentCommand(
                title=titles[0],
                source_filename="catalog.txt",
                media_type="text/plain",
                content=content,
            ),
        )

        summaries = await document_list.list_documents(
            workspace_id=LEGACY_WORKSPACE_ID, status="active"
        )
        summary = next(
            item for item in summaries if item.document_id == created.document_id
        )
        assert summary.title == titles[0]
        assert summary.active_version_id == created.version_id
        assert summary.active_version_number == 1
        assert summary.source_filename == "catalog.txt"
        assert summary.chunk_count == created.chunk_count

        with pytest.raises(DuplicateDocumentContentError) as error:
            await ingestion.execute(
                LEGACY_WORKSPACE_ID,
                IngestNewDocumentCommand(
                    title=titles[1],
                    source_filename="same-content.txt",
                    media_type="text/plain",
                    content=content,
                ),
            )
        assert error.value.document_id == created.document_id
    finally:
        async with session_factory() as session:
            await session.execute(delete(Document).where(Document.title.in_(titles)))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_workspace_scope_blocks_cross_tenant_reads_and_mutations() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)
    provider = DeterministicEmbeddingProvider(dimension=1536)
    ingestion = IngestNewDocument(
        embedding_provider=provider,
        unit_of_work_factory=SqlAlchemyIngestionUnitOfWorkFactory(session_factory),
    )
    document_list = SqlAlchemyDocumentListRepository(session_factory)
    lifecycle = SqlAlchemyDocumentLifecycleRepository(session_factory)
    versions = SqlAlchemyDocumentVersionRepository(session_factory)
    search = SearchDocuments(
        embedding_provider=provider,
        repository=SqlAlchemyChunkSearchRepository(session_factory),
    )
    first_workspace = Workspace(name="Isolation workspace A")
    second_workspace = Workspace(name="Isolation workspace B")
    first_knowledge_base = KnowledgeBase(
        workspace=first_workspace, name="General", is_default=True
    )
    second_knowledge_base = KnowledgeBase(
        workspace=second_workspace, name="General", is_default=True
    )

    try:
        async with session_factory() as session:
            session.add_all(
                [
                    first_workspace,
                    second_workspace,
                    first_knowledge_base,
                    second_knowledge_base,
                ]
            )
            await session.commit()

        first = await ingestion.execute(
            first_workspace.id,
            IngestNewDocumentCommand(
                title="Workspace A private fixture",
                source_filename="workspace-a.txt",
                media_type="text/plain",
                content=b"private alpha tenant evidence",
            ),
        )
        second = await ingestion.execute(
            second_workspace.id,
            IngestNewDocumentCommand(
                title="Workspace B private fixture",
                source_filename="workspace-b.txt",
                media_type="text/plain",
                content=b"private beta tenant evidence",
            ),
        )

        first_list = await document_list.list_documents(
            workspace_id=first_workspace.id, status="active"
        )
        assert [item.document_id for item in first_list] == [first.document_id]
        assert second.document_id not in {item.document_id for item in first_list}

        results = await search.execute(
            SearchDocumentsCommand(
                query="private alpha tenant evidence",
                workspace_id=first_workspace.id,
                limit=20,
            )
        )
        assert results
        assert {item.document_id for item in results} == {first.document_id}

        assert await lifecycle.archive(second_workspace.id, first.document_id) is False
        with pytest.raises(DocumentNotFoundError):
            await versions.list_versions(second_workspace.id, first.document_id)
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(Document).where(
                    Document.workspace_id.in_([first_workspace.id, second_workspace.id])
                )
            )
            await session.execute(
                delete(KnowledgeBase).where(
                    KnowledgeBase.workspace_id.in_(
                        [first_workspace.id, second_workspace.id]
                    )
                )
            )
            await session.execute(
                delete(Workspace).where(
                    Workspace.id.in_([first_workspace.id, second_workspace.id])
                )
            )
            await session.commit()
        await engine.dispose()
