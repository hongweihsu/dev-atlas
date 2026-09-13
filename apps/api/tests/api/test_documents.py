from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from devatlas.api.routes.documents import (
    get_ingest_new_document,
    get_list_documents,
    get_manage_document_lifecycle,
    get_manage_document_versions,
)
from devatlas.application.ingest_document import IngestNewDocument
from devatlas.application.list_documents import ListDocuments
from devatlas.application.manage_document_lifecycle import ManageDocumentLifecycle
from devatlas.application.manage_document_versions import ManageDocumentVersions
from devatlas.application.ports.document_list import DocumentSummary
from devatlas.application.ports.document_versions import DocumentVersionSummary
from devatlas.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProviderUnavailableError,
)
from devatlas.application.ports.persistence import DocumentNotFoundError
from devatlas.domain.document_ingestion import DEFAULT_MAX_TEXT_BYTES
from devatlas.main import app
from tests.fakes import (
    DeterministicEmbeddingProvider,
    FakeIngestionUnitOfWorkFactory,
)

TEST_WORKSPACE_ID = UUID(int=999)


@pytest.fixture
def ingestion_client() -> Iterator[tuple[TestClient, FakeIngestionUnitOfWorkFactory]]:
    factory = FakeIngestionUnitOfWorkFactory()
    service = IngestNewDocument(
        embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        unit_of_work_factory=factory,
        expected_embedding_dimension=8,
    )
    app.dependency_overrides[get_ingest_new_document] = lambda: service
    try:
        yield TestClient(app), factory
    finally:
        app.dependency_overrides.clear()


def test_post_document_returns_ready_provenance(
    ingestion_client: tuple[TestClient, FakeIngestionUnitOfWorkFactory],
) -> None:
    client, factory = ingestion_client

    response = client.post(
        "/documents",
        data={"title": "  Architecture notes  "},
        files={"file": ("notes.txt", b"transaction boundaries", "text/plain")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "notes.txt"
    assert body["status"] == "ready"
    assert body["chunk_count"] == 1
    assert body["version_number"] == 1
    assert body["document_id"] == str(factory.committed_documents[0].id)
    assert body["version_id"] == str(factory.committed_documents[0].version.id)
    assert factory.committed_documents[0].title == "Architecture notes"


def test_post_document_defaults_blank_title_to_filename(
    ingestion_client: tuple[TestClient, FakeIngestionUnitOfWorkFactory],
) -> None:
    client, factory = ingestion_client

    response = client.post(
        "/documents",
        files={"file": ("architecture-notes.txt", b"content", "text/plain")},
    )

    assert response.status_code == 201
    assert factory.committed_documents[0].title == "architecture-notes"


def test_get_documents_returns_active_version_summaries() -> None:
    service = AsyncMock(spec=ListDocuments)
    service.execute.return_value = [
        DocumentSummary(
            document_id=uuid4(),
            title="Architecture notes",
            active_version_id=uuid4(),
            active_version_number=2,
            source_filename="notes-v2.txt",
            chunk_count=3,
            updated_at=datetime(2026, 9, 9, tzinfo=UTC),
            archived_at=None,
        )
    ]
    app.dependency_overrides[get_list_documents] = lambda: service
    try:
        response = TestClient(app).get("/documents")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["title"] == "Architecture notes"
    assert response.json()[0]["active_version_number"] == 2
    assert response.json()[0]["chunk_count"] == 3


def test_document_version_routes_list_and_activate_immutable_version() -> None:
    document_id = uuid4()
    version_id = uuid4()
    service = AsyncMock(spec=ManageDocumentVersions)
    service.list_versions.return_value = [
        DocumentVersionSummary(
            version_id=version_id,
            version_number=1,
            source_filename="notes.txt",
            media_type="text/plain",
            content_checksum="a" * 64,
            character_count=21,
            chunk_count=1,
            embedding_model="text-embedding-3-small",
            embedding_dimension=1536,
            is_active=False,
            created_at=datetime(2026, 9, 12, tzinfo=UTC),
        )
    ]
    app.dependency_overrides[get_manage_document_versions] = lambda: service
    try:
        client = TestClient(app)
        listed = client.get(f"/documents/{document_id}/versions")
        activated = client.post(
            f"/documents/{document_id}/versions/{version_id}/activate"
        )
    finally:
        app.dependency_overrides.clear()

    assert listed.status_code == 200
    assert listed.json()[0]["version_id"] == str(version_id)
    assert listed.json()[0]["is_active"] is False
    assert activated.status_code == 204
    service.activate_version.assert_awaited_once_with(
        TEST_WORKSPACE_ID, document_id, version_id
    )


def test_document_lifecycle_routes_archive_restore_and_map_missing() -> None:
    document_id = uuid4()
    service = AsyncMock(spec=ManageDocumentLifecycle)
    app.dependency_overrides[get_manage_document_lifecycle] = lambda: service
    try:
        client = TestClient(app)
        archived = client.delete(f"/documents/{document_id}")
        restored = client.post(f"/documents/{document_id}/restore")
        service.archive.side_effect = DocumentNotFoundError("document was not found")
        missing = client.delete(f"/documents/{uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert archived.status_code == 204
    assert restored.status_code == 204
    service.archive.assert_awaited()
    service.restore.assert_awaited_once_with(TEST_WORKSPACE_ID, document_id)
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "document_not_found"


def test_post_document_duplicate_returns_existing_document_id(
    ingestion_client: tuple[TestClient, FakeIngestionUnitOfWorkFactory],
) -> None:
    client, _ = ingestion_client
    first = client.post(
        "/documents",
        data={"title": "First title"},
        files={"file": ("notes.txt", b"same content", "text/plain")},
    )

    duplicate = client.post(
        "/documents",
        data={"title": "Different title"},
        files={"file": ("copy.txt", b"same content", "text/plain")},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == {
        "code": "duplicate_document_content",
        "message": "this content already exists in another document",
        "document_id": first.json()["document_id"],
        "document_archived": False,
    }


@pytest.mark.parametrize(
    ("filename", "content", "media_type", "expected_status", "expected_code"),
    [
        ("notes.pdf", b"text", "application/pdf", 422, "invalid_pdf"),
        (
            "notes.txt",
            b"a" * (DEFAULT_MAX_TEXT_BYTES + 1),
            "text/plain",
            413,
            "file_too_large",
        ),
        ("notes.txt", b"\xff", "text/plain", 422, "invalid_utf8"),
        ("notes.txt", b"  \n", "text/plain", 422, "empty_content"),
    ],
)
def test_post_document_maps_safe_validation_errors(
    ingestion_client: tuple[TestClient, FakeIngestionUnitOfWorkFactory],
    filename: str,
    content: bytes,
    media_type: str,
    expected_status: int,
    expected_code: str,
) -> None:
    client, factory = ingestion_client

    response = client.post(
        "/documents",
        data={"title": "Notes"},
        files={"file": (filename, content, media_type)},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"]["code"] == expected_code
    assert factory.committed_documents == []


@pytest.mark.parametrize("title", ["a" * 256])
def test_post_document_rejects_invalid_title(
    ingestion_client: tuple[TestClient, FakeIngestionUnitOfWorkFactory],
    title: str,
) -> None:
    client, factory = ingestion_client

    response = client.post(
        "/documents",
        data={"title": title},
        files={"file": ("notes.txt", b"content", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_title"
    assert factory.committed_documents == []


def test_post_document_reports_unconfigured_runtime() -> None:
    response = TestClient(app).post(
        "/documents",
        data={"title": "Notes"},
        files={"file": ("notes.txt", b"content", "text/plain")},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "ingestion_unavailable"


def test_post_document_requires_file(
    ingestion_client: tuple[TestClient, FakeIngestionUnitOfWorkFactory],
) -> None:
    client, factory = ingestion_client

    response = client.post("/documents", data={"title": "Notes"})

    assert response.status_code == 422
    assert factory.committed_documents == []


def test_post_document_maps_embedding_provider_failure() -> None:
    service = AsyncMock(spec=IngestNewDocument)
    service.execute.side_effect = EmbeddingProviderUnavailableError(
        "embedding provider request failed"
    )
    app.dependency_overrides[get_ingest_new_document] = lambda: service
    try:
        response = TestClient(app).post(
            "/documents",
            data={"title": "Notes"},
            files={"file": ("notes.txt", b"content", "text/plain")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "embedding_unavailable",
        "message": "embedding provider request failed",
    }


def test_post_document_maps_incompatible_embedding_response() -> None:
    service = AsyncMock(spec=IngestNewDocument)
    service.execute.side_effect = EmbeddingBatchError("invalid provider indices")
    app.dependency_overrides[get_ingest_new_document] = lambda: service
    try:
        response = TestClient(app).post(
            "/documents",
            data={"title": "Notes"},
            files={"file": ("notes.txt", b"content", "text/plain")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json()["detail"] == {
        "code": "invalid_embedding_response",
        "message": "invalid provider indices",
    }


def test_post_document_version_returns_next_version(
    ingestion_client: tuple[TestClient, FakeIngestionUnitOfWorkFactory],
) -> None:
    client, _ = ingestion_client
    created = client.post(
        "/documents",
        data={"title": "Architecture notes"},
        files={"file": ("notes.txt", b"first content", "text/plain")},
    ).json()

    response = client.post(
        f"/documents/{created['document_id']}/versions",
        files={"file": ("notes-v2.txt", b"changed content", "text/plain")},
    )

    assert response.status_code == 201
    assert response.json()["document_id"] == created["document_id"]
    assert response.json()["version_number"] == 2


def test_post_document_version_rejects_duplicate_content(
    ingestion_client: tuple[TestClient, FakeIngestionUnitOfWorkFactory],
) -> None:
    client, _ = ingestion_client
    created = client.post(
        "/documents",
        data={"title": "Architecture notes"},
        files={"file": ("notes.txt", b"same content", "text/plain")},
    ).json()

    response = client.post(
        f"/documents/{created['document_id']}/versions",
        files={"file": ("notes-again.txt", b"same content", "text/plain")},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "duplicate_document_content"


def test_post_document_version_rejects_unknown_document(
    ingestion_client: tuple[TestClient, FakeIngestionUnitOfWorkFactory],
) -> None:
    client, _ = ingestion_client

    response = client.post(
        f"/documents/{uuid4()}/versions",
        files={"file": ("notes.txt", b"content", "text/plain")},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "document_not_found"
