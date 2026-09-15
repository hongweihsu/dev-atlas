from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import AsyncOpenAI

from devatlas.infrastructure.generation.openai_corrective_query import (
    OpenAICorrectiveQueryGenerator,
    _CorrectiveQuery,
)


@pytest.mark.asyncio
async def test_requests_a_bounded_query_only_rewrite() -> None:
    parse = AsyncMock(
        return_value=SimpleNamespace(
            output_parsed=_CorrectiveQuery(query="database transaction boundary")
        )
    )
    client = MagicMock(spec=AsyncOpenAI)
    client.responses.parse = parse

    query = await OpenAICorrectiveQueryGenerator(cast(AsyncOpenAI, client)).rewrite(
        "Why does it matter?", "Evidence is insufficient"
    )

    assert query == "database transaction boundary"
    assert parse.await_args is not None
    kwargs = parse.await_args.kwargs
    assert kwargs["text_format"] is _CorrectiveQuery
    assert kwargs["store"] is False
    assert "Do not answer" in kwargs["instructions"]
