from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from devatlas.application.ports.agentic_research import (
    InvalidResearchQuestionError,
    ResearchAgent,
    ResearchResult,
)
from devatlas.application.run_agentic_research import (
    MAX_RESEARCH_QUESTION_CHARACTERS,
    RunAgenticResearch,
    RunAgenticResearchCommand,
)


@pytest.mark.asyncio
async def test_normalizes_question_before_running_agent() -> None:
    agent = AsyncMock(spec=ResearchAgent)
    agent.research.return_value = ResearchResult(
        answer="Result",
        has_sufficient_evidence=True,
        steps=(),
        citations=(),
        stop_reason="completed",
    )
    workspace_id = uuid4()

    result = await RunAgenticResearch(agent).execute(
        RunAgenticResearchCommand(
            question="  Compare them  ", workspace_id=workspace_id
        )
    )

    assert result.answer == "Result"
    agent.research.assert_awaited_once_with("Compare them", workspace_id=workspace_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question", ["  ", "x" * (MAX_RESEARCH_QUESTION_CHARACTERS + 1)]
)
async def test_rejects_invalid_question(question: str) -> None:
    agent = AsyncMock(spec=ResearchAgent)

    with pytest.raises(InvalidResearchQuestionError):
        await RunAgenticResearch(agent).execute(
            RunAgenticResearchCommand(question=question, workspace_id=uuid4())
        )

    agent.research.assert_not_awaited()
