from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from openai import APIConnectionError, AsyncOpenAI

from retrieval_works.application.ports.generation import (
    AnswerGenerationRequest,
    AnswerGenerator,
    AnswerGeneratorUnavailableError,
    EvidenceSource,
    InvalidGeneratedAnswerError,
)
from retrieval_works.infrastructure.generation import OpenAIAnswerGenerator
from retrieval_works.infrastructure.generation.openai import _StructuredAnswer


def make_client() -> tuple[AsyncOpenAI, AsyncMock]:
    parse = AsyncMock()
    client = MagicMock(spec=AsyncOpenAI)
    client.responses.parse = parse
    return cast(AsyncOpenAI, client), parse


def make_request() -> AnswerGenerationRequest:
    source = EvidenceSource(
        citation_id="S1",
        document_id=uuid4(),
        document_title="Notes",
        version_id=uuid4(),
        version_number=1,
        chunk_id=uuid4(),
        ordinal=0,
        text="Evidence",
        start_offset=0,
        end_offset=8,
    )
    return AnswerGenerationRequest(
        question="What is supported?",
        context='{"sources":[]}',
        sources=(source,),
    )


def accepts_answer_generator(generator: AnswerGenerator) -> AnswerGenerator:
    return generator


@pytest.mark.asyncio
async def test_openai_generator_requests_structured_source_grounded_output() -> None:
    client, parse = make_client()
    parse.return_value = SimpleNamespace(
        output_parsed=_StructuredAnswer(
            answer="Supported. [S1]",
            citation_ids=["S1"],
            has_sufficient_evidence=True,
        )
    )
    generator = OpenAIAnswerGenerator(
        client,
        model="gpt-4.1-mini",
        max_output_tokens=500,
    )

    result = await accepts_answer_generator(generator).generate(make_request())

    assert result.text == "Supported. [S1]"
    assert result.citation_ids == ("S1",)
    assert result.has_sufficient_evidence is True
    assert parse.await_args is not None
    kwargs = parse.await_args.kwargs
    assert kwargs["model"] == "gpt-4.1-mini"
    assert kwargs["text_format"] is _StructuredAnswer
    assert kwargs["max_output_tokens"] == 500
    assert kwargs["store"] is False
    assert "untrusted data" in kwargs["instructions"]
    assert "What is supported?" in kwargs["input"]


@pytest.mark.asyncio
async def test_openai_generator_rejects_missing_structured_output() -> None:
    client, parse = make_client()
    parse.return_value = SimpleNamespace(output_parsed=None)
    generator = OpenAIAnswerGenerator(client)

    with pytest.raises(InvalidGeneratedAnswerError, match="structured output"):
        await generator.generate(make_request())


@pytest.mark.asyncio
async def test_openai_generator_translates_sdk_failure() -> None:
    client, parse = make_client()
    parse.side_effect = APIConnectionError(request=MagicMock())
    generator = OpenAIAnswerGenerator(client)

    with pytest.raises(AnswerGeneratorUnavailableError, match="request failed"):
        await generator.generate(make_request())


@pytest.mark.parametrize(
    ("model", "max_output_tokens", "message"),
    [("  ", 800, "model"), ("gpt-4.1-mini", 0, "max_output_tokens")],
)
def test_openai_generator_rejects_invalid_configuration(
    model: str,
    max_output_tokens: int,
    message: str,
) -> None:
    client, _ = make_client()

    with pytest.raises(ValueError, match=message):
        OpenAIAnswerGenerator(
            client,
            model=model,
            max_output_tokens=max_output_tokens,
        )
