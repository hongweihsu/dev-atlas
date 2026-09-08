from collections.abc import Iterator
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from devatlas.api.routes.documents import get_ingest_new_document
from devatlas.application.ingest_document import IngestNewDocument
from devatlas.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProviderUnavailableError,
)
from devatlas.domain.document_ingestion import DEFAULT_MAX_TEXT_BYTES
from devatlas.main import app
from tests.fakes import (
    DeterministicEmbeddingProvider,
    FakeIngestionUnitOfWorkFactory,
)


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


@pytest.mark.parametrize(
    ("filename", "content", "media_type", "expected_status", "expected_code"),
    [
        ("notes.pdf", b"text", "application/pdf", 415, "unsupported_type"),
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


@pytest.mark.parametrize("title", ["", "   ", "a" * 256])
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
