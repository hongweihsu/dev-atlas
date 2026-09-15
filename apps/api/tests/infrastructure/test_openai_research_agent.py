from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from openai import AsyncOpenAI

from devatlas.application.manage_knowledge_bases import ManageKnowledgeBases
from devatlas.application.ports.agentic_research import InvalidResearchResponseError
from devatlas.application.ports.knowledge_bases import KnowledgeBaseSummary
from devatlas.application.ports.retrieval import RetrievedChunk
from devatlas.application.search_documents import SearchDocuments
from devatlas.infrastructure.generation.openai_research_agent import (
    LIST_KNOWLEDGE_BASES_TOOL,
    MAX_RESEARCH_TOOL_CALLS,
    SEARCH_DOCUMENTS_TOOL,
    OpenAIResearchAgent,
    _StructuredResearchAnswer,
)


def call(name: str, arguments: str, number: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        type="function_call",
        name=name,
        arguments=arguments,
        call_id=f"call-{number}",
    )


def response(
    *, output: list[object], parsed: _StructuredResearchAnswer | None = None
) -> SimpleNamespace:
    return SimpleNamespace(output=output, output_parsed=parsed)


def make_agent() -> tuple[OpenAIResearchAgent, AsyncMock, AsyncMock, AsyncMock]:
    parse = AsyncMock()
    client = MagicMock(spec=AsyncOpenAI)
    client.responses.parse = parse
    knowledge_bases = AsyncMock(spec=ManageKnowledgeBases)
    search = AsyncMock(spec=SearchDocuments)
    return (
        OpenAIResearchAgent(
            cast(AsyncOpenAI, client),
            knowledge_bases=knowledge_bases,
            search_documents=search,
        ),
        parse,
        knowledge_bases,
        search,
    )


@pytest.mark.asyncio
async def test_model_lists_then_searches_and_returns_validated_citation() -> None:
    agent, parse, knowledge_bases, search = make_agent()
    knowledge_base_id = uuid4()
    workspace_id = uuid4()
    chunk_id = uuid4()
    knowledge_bases.list.return_value = [
        KnowledgeBaseSummary(
            id=knowledge_base_id,
            name="Backend",
            is_default=False,
            document_count=2,
        )
    ]
    knowledge_bases.resolve_scope.return_value = (knowledge_base_id,)
    chunk = RetrievedChunk(
        document_id=uuid4(),
        document_title="Transactions",
        version_id=uuid4(),
        version_number=1,
        chunk_id=chunk_id,
        ordinal=0,
        text="A unit of work commits one transaction.",
        start_offset=0,
        end_offset=39,
        score=0.1,
        scoring_method="rrf",
    )
    search.execute.return_value = [chunk]
    citation_id = f"C{chunk_id}"
    parse.side_effect = [
        response(output=[call(LIST_KNOWLEDGE_BASES_TOOL, "{}")]),
        response(
            output=[
                call(
                    SEARCH_DOCUMENTS_TOOL,
                    '{"query":"transactions","knowledge_base_ids":'
                    f'["{knowledge_base_id}"],"limit":3}}',
                    2,
                )
            ]
        ),
        response(
            output=[],
            parsed=_StructuredResearchAnswer(
                answer="The unit of work commits one transaction.",
                citation_ids=[citation_id],
                has_sufficient_evidence=True,
            ),
        ),
    ]

    result = await agent.research("Explain transactions", workspace_id=workspace_id)

    assert [step.tool_name for step in result.steps] == [
        LIST_KNOWLEDGE_BASES_TOOL,
        SEARCH_DOCUMENTS_TOOL,
    ]
    assert result.citations[0].chunk_id == chunk_id
    assert result.stop_reason == "completed"
    knowledge_bases.list.assert_awaited_once_with(workspace_id)
    knowledge_bases.resolve_scope.assert_awaited_once_with(
        workspace_id, (knowledge_base_id,)
    )
    assert all(
        item.kwargs["parallel_tool_calls"] is False for item in parse.await_args_list
    )
    assert [item.kwargs["tool_choice"] for item in parse.await_args_list] == [
        "auto",
        "auto",
        "auto",
    ]


@pytest.mark.asyncio
async def test_budget_forces_final_answer_without_another_tool() -> None:
    agent, parse, knowledge_bases, _ = make_agent()
    knowledge_bases.list.return_value = []
    parse.side_effect = [
        *[
            response(output=[call(LIST_KNOWLEDGE_BASES_TOOL, "{}", number)])
            for number in range(1, MAX_RESEARCH_TOOL_CALLS + 1)
        ],
        response(
            output=[],
            parsed=_StructuredResearchAnswer(
                answer="No knowledge bases are available.",
                citation_ids=[],
                has_sufficient_evidence=True,
            ),
        ),
    ]

    result = await agent.research("What is available?", workspace_id=uuid4())

    assert len(result.steps) == MAX_RESEARCH_TOOL_CALLS
    assert result.stop_reason == "tool_budget_reached"
    assert parse.await_args_list[-1].kwargs["tool_choice"] == "none"


@pytest.mark.asyncio
async def test_rejects_citation_that_no_search_returned() -> None:
    agent, parse, _, _ = make_agent()
    parse.return_value = response(
        output=[],
        parsed=_StructuredResearchAnswer(
            answer="Unsupported",
            citation_ids=["C-forged"],
            has_sufficient_evidence=True,
        ),
    )

    with pytest.raises(InvalidResearchResponseError, match="unknown citation"):
        await agent.research("Question", workspace_id=uuid4())
