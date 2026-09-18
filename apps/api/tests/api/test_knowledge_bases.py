from collections.abc import Iterator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from retrieval_works.api.routes.knowledge_bases import get_manage_knowledge_bases
from retrieval_works.application.manage_knowledge_bases import ManageKnowledgeBases
from retrieval_works.application.ports.knowledge_bases import KnowledgeBaseSummary
from retrieval_works.main import app


@pytest.fixture
def service() -> Iterator[AsyncMock]:
    mocked = AsyncMock(spec=ManageKnowledgeBases)
    app.dependency_overrides[get_manage_knowledge_bases] = lambda: mocked
    try:
        yield mocked
    finally:
        app.dependency_overrides.clear()


def test_list_and_create_knowledge_bases(service: AsyncMock) -> None:
    general = KnowledgeBaseSummary(
        id=uuid4(), name="General", is_default=True, document_count=3
    )
    service.list.return_value = [general]
    service.create.return_value = KnowledgeBaseSummary(
        id=uuid4(), name="Backend", is_default=False, document_count=0
    )
    client = TestClient(app)

    listed = client.get("/knowledge-bases")
    created = client.post("/knowledge-bases", json={"name": " Backend "})

    assert listed.status_code == 200
    assert listed.json()[0]["document_count"] == 3
    assert created.status_code == 201
    assert created.json()["name"] == "Backend"
    service.create.assert_awaited_once_with(UUID(int=999), " Backend ")
