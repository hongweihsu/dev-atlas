from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import AsyncOpenAI

from devatlas.application.ports.document_extraction import (
    DocumentExtractionUnavailableError,
)
from devatlas.domain.document_ingestion import PageSpan, PreparedTextDocument
from devatlas.infrastructure.extraction.openai_pdf import (
    OpenAIMultimodalDocumentExtractor,
)


def make_client() -> tuple[AsyncOpenAI, AsyncMock]:
    parse = AsyncMock()
    client = MagicMock(spec=AsyncOpenAI)
    client.responses.parse = parse
    return cast(AsyncOpenAI, client), parse


@pytest.mark.asyncio
async def test_native_pdf_text_does_not_call_multimodal_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, parse = make_client()
    native = PreparedTextDocument(
        source_filename="guide.pdf",
        media_type="application/pdf",
        normalized_text="Native text",
        content_checksum="checksum",
        byte_size=3,
        character_count=11,
        page_spans=(PageSpan(1, 0, 11),),
    )
    monkeypatch.setattr(
        "devatlas.infrastructure.extraction.openai_pdf.prepare_document",
        lambda **_kwargs: native,
    )
    extractor = OpenAIMultimodalDocumentExtractor(client)

    result = await extractor.prepare(
        content=b"pdf", source_filename="guide.pdf", media_type="application/pdf"
    )

    assert result is native
    parse.assert_not_awaited()


@pytest.mark.asyncio
async def test_textless_pdf_uses_structured_multimodal_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, parse = make_client()
    monkeypatch.setattr(
        "devatlas.infrastructure.extraction.openai_pdf.prepare_document",
        lambda **_kwargs: PreparedTextDocument(
            source_filename="scan.pdf",
            media_type="application/pdf",
            normalized_text="Partial",
            content_checksum="checksum",
            byte_size=3,
            character_count=7,
            page_spans=(PageSpan(1, 0, 7),),
            pages_without_text=(2,),
        ),
    )
    parse.return_value = SimpleNamespace(
        output_parsed=SimpleNamespace(
            pages=[
                SimpleNamespace(page_number=1, markdown="First page"),
                SimpleNamespace(
                    page_number=2,
                    markdown="| Code | Value |\n| --- | --- |\n| DA-42 | Ready |",
                ),
            ]
        )
    )
    extractor = OpenAIMultimodalDocumentExtractor(client, model="gpt-4.1-mini")

    result = await extractor.prepare(
        content=b"pdf", source_filename="scan.pdf", media_type="application/pdf"
    )

    assert result.page_spans == (PageSpan(1, 0, 10), PageSpan(2, 12, 60))
    assert "| DA-42 | Ready |" in result.normalized_text
    assert parse.await_args is not None
    request = parse.await_args.kwargs
    assert request["store"] is False
    assert request["input"][0]["content"][0]["detail"] == "high"


@pytest.mark.asyncio
async def test_multimodal_extraction_rejects_duplicate_page_numbers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, parse = make_client()
    monkeypatch.setattr(
        "devatlas.infrastructure.extraction.openai_pdf.prepare_document",
        lambda **_kwargs: PreparedTextDocument(
            source_filename="scan.pdf",
            media_type="application/pdf",
            normalized_text="Partial",
            content_checksum="checksum",
            byte_size=3,
            character_count=7,
            pages_without_text=(2,),
        ),
    )
    parse.return_value = SimpleNamespace(
        output_parsed=SimpleNamespace(
            pages=[
                SimpleNamespace(page_number=1, markdown="One"),
                SimpleNamespace(page_number=1, markdown="Duplicate"),
            ]
        )
    )
    extractor = OpenAIMultimodalDocumentExtractor(client)

    with pytest.raises(DocumentExtractionUnavailableError, match="page ordering"):
        await extractor.prepare(
            content=b"pdf", source_filename="scan.pdf", media_type="application/pdf"
        )
