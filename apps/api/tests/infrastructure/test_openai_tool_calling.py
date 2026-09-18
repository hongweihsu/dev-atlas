import json
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from openai import AsyncOpenAI

from retrieval_works.application.manage_knowledge_bases import ManageKnowledgeBases
from retrieval_works.application.ports.knowledge_bases import KnowledgeBaseSummary
from retrieval_works.application.ports.tool_calling import InvalidToolCallError
from retrieval_works.infrastructure.generation.openai_tool_calling import (
    LIST_KNOWLEDGE_BASES_TOOL,
    OpenAIWorkspaceQuestionAnswerer,
)


def make_client() -> tuple[AsyncOpenAI, AsyncMock]:
    create = AsyncMock()
    client = MagicMock(spec=AsyncOpenAI)
    client.responses.create = create
    return cast(AsyncOpenAI, client), create


@pytest.mark.asyncio
async def test_executes_one_scoped_tool_and_returns_its_trace() -> None:
    client, create = make_client()
    call = SimpleNamespace(
        type="function_call",
        name=LIST_KNOWLEDGE_BASES_TOOL,
        arguments="{}",
        call_id="call-1",
    )
    create.side_effect = [
        SimpleNamespace(output=[call]),
        SimpleNamespace(output=[], output_text="Backend has the most documents."),
    ]
    knowledge_bases = AsyncMock(spec=ManageKnowledgeBases)
    knowledge_bases.list.return_value = [
        KnowledgeBaseSummary(
            id=uuid4(), name="Backend", is_default=False, document_count=4
        )
    ]
    workspace_id = uuid4()
    answerer = OpenAIWorkspaceQuestionAnswerer(client, knowledge_bases)

    result = await answerer.answer(
        "Which knowledge base has the most documents?", workspace_id=workspace_id
    )

    assert result.text == "Backend has the most documents."
    assert result.tools[0].name == LIST_KNOWLEDGE_BASES_TOOL
    knowledge_bases.list.assert_awaited_once_with(workspace_id)
    assert create.await_count == 2
    first_request = create.await_args_list[0].kwargs
    assert first_request["tool_choice"] == "required"
    assert first_request["parallel_tool_calls"] is False
    assert first_request["tools"][0]["strict"] is True
    assert "workspace_id" not in json.dumps(first_request["tools"])
    final_request = create.await_args_list[1].kwargs
    assert final_request["tool_choice"] == "none"
    tool_output = final_request["input"][-1]
    assert tool_output["type"] == "function_call_output"
    assert '"document_count": 4' in tool_output["output"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call",
    [
        SimpleNamespace(
            type="function_call",
            name="delete_everything",
            arguments="{}",
            call_id="call-1",
        ),
        SimpleNamespace(
            type="function_call",
            name=LIST_KNOWLEDGE_BASES_TOOL,
            arguments='{"workspace_id":"forged"}',
            call_id="call-1",
        ),
    ],
)
async def test_rejects_unknown_tool_or_extra_arguments(call: object) -> None:
    client, create = make_client()
    create.return_value = SimpleNamespace(output=[call])
    knowledge_bases = AsyncMock(spec=ManageKnowledgeBases)
    answerer = OpenAIWorkspaceQuestionAnswerer(client, knowledge_bases)

    with pytest.raises(InvalidToolCallError):
        await answerer.answer("Question", workspace_id=uuid4())

    knowledge_bases.list.assert_not_awaited()
    assert create.await_count == 1


@pytest.mark.asyncio
async def test_rejects_multiple_tool_calls() -> None:
    client, create = make_client()
    call = SimpleNamespace(
        type="function_call",
        name=LIST_KNOWLEDGE_BASES_TOOL,
        arguments="{}",
        call_id="call-1",
    )
    create.return_value = SimpleNamespace(output=[call, call])
    answerer = OpenAIWorkspaceQuestionAnswerer(
        client, AsyncMock(spec=ManageKnowledgeBases)
    )

    with pytest.raises(InvalidToolCallError, match="exactly one"):
        await answerer.answer("Question", workspace_id=uuid4())
