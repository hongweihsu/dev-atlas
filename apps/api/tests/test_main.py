from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

import devatlas.main as main_module
from devatlas.application.answer_documents import AnswerDocuments
from devatlas.application.ingest_document import IngestNewDocument
from devatlas.application.list_documents import ListDocuments
from devatlas.application.search_documents import SearchDocuments
from devatlas.core.config import Settings


def test_settings_parse_schema_dimension_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBEDDING_DIMENSION", "1536")

    assert Settings().embedding_dimension == 1536


def test_settings_reject_mixed_local_and_oidc_authentication() -> None:
    with pytest.raises(ValueError, match="either auth_jwt_secret or auth_jwks_url"):
        Settings(
            auth_jwt_secret=SecretStr("local-secret"),
            auth_jwks_url="https://identity.example.com/.well-known/jwks.json",
        )


def test_lifespan_wires_and_releases_ingestion_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = MagicMock(spec=AsyncEngine)
    engine.dispose = AsyncMock()
    client = MagicMock(spec=AsyncOpenAI)
    client.close = AsyncMock()
    session_factory = MagicMock(return_value=MagicMock(spec=AsyncSession))
    monkeypatch.setattr(main_module, "create_database_engine", lambda _url: engine)
    monkeypatch.setattr(
        main_module,
        "create_session_factory",
        lambda _engine: session_factory,
    )
    monkeypatch.setattr(main_module, "AsyncOpenAI", lambda **_kwargs: client)
    application = main_module.create_app(Settings(openai_api_key=SecretStr("test-key")))

    with TestClient(application):
        assert isinstance(
            application.state.ingest_new_document,
            IngestNewDocument,
        )
        assert isinstance(application.state.list_documents, ListDocuments)
        assert isinstance(application.state.search_documents, SearchDocuments)
        assert isinstance(application.state.answer_documents, AnswerDocuments)

    assert not hasattr(application.state, "ingest_new_document")
    assert not hasattr(application.state, "search_documents")
    assert not hasattr(application.state, "answer_documents")
    assert not hasattr(application.state, "list_documents")
    client.close.assert_awaited_once()
    engine.dispose.assert_awaited_once()


def test_lifespan_leaves_ingestion_unconfigured_without_api_key() -> None:
    application = main_module.create_app(Settings(openai_api_key=None))

    with TestClient(application):
        assert isinstance(application.state.list_documents, ListDocuments)
        assert not hasattr(application.state, "ingest_new_document")
        assert not hasattr(application.state, "search_documents")
        assert not hasattr(application.state, "answer_documents")

    assert not hasattr(application.state, "list_documents")
