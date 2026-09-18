from collections.abc import Iterator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from retrieval_works.api.routes.research import get_run_agentic_research
from retrieval_works.application.ports.agentic_research import (
    ResearchResult,
    ResearchStep,
)
from retrieval_works.application.ports.generation import EvidenceSource
from retrieval_works.application.run_agentic_research import RunAgenticResearch
from retrieval_works.main import app


@pytest.fixture
def service() -> Iterator[AsyncMock]:
    mocked = AsyncMock(spec=RunAgenticResearch)
    app.dependency_overrides[get_run_agentic_research] = lambda: mocked
    try:
        yield mocked
    finally:
        app.dependency_overrides.clear()


def test_returns_agent_steps_stop_reason_and_citations(service: AsyncMock) -> None:
    source = EvidenceSource(
        citation_id="C1",
        document_id=uuid4(),
        document_title="Transactions",
        version_id=uuid4(),
        version_number=1,
        chunk_id=uuid4(),
        ordinal=0,
        text="A unit of work commits once.",
        start_offset=0,
        end_offset=28,
    )
    service.execute.return_value = ResearchResult(
        answer="It commits once.",
        has_sufficient_evidence=True,
        steps=(
            ResearchStep(
                ordinal=0,
                tool_name="search_documents",
                summary="Searched documents and found 1 chunks",
            ),
        ),
        citations=(source,),
        stop_reason="completed",
    )

    response = TestClient(app).post(
        "/research", json={"question": "Explain transaction boundaries"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "It commits once."
    assert body["stop_reason"] == "completed"
    assert body["steps"][0]["tool_name"] == "search_documents"
    assert body["citations"][0]["citation_id"] == "C1"
    command = service.execute.await_args.args[0]
    assert command.workspace_id == UUID(int=999)
