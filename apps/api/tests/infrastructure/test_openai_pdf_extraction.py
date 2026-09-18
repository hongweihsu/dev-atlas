from io import BytesIO
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import AsyncOpenAI
from pypdf import PdfReader, PdfWriter

from devatlas.application.ports.document_extraction import (
    DocumentExtractionUnavailableError,
)
from devatlas.domain.document_ingestion import PageSpan, PreparedTextDocument
from devatlas.infrastructure.extraction.openai_pdf import (
    OpenAIMultimodalDocumentExtractor,
    _select_pdf_pages,
)
from devatlas.infrastructure.extraction.pdf_layout import PdfPageLayout


def make_client() -> tuple[AsyncOpenAI, AsyncMock]:
    parse = AsyncMock()
    client = MagicMock(spec=AsyncOpenAI)
    client.responses.parse = parse
    return cast(AsyncOpenAI, client), parse


def layout(*reasons: str) -> tuple[PdfPageLayout, ...]:
    return (
        PdfPageLayout(
            page_number=1,
            has_text=True,
            table_rectangle_count=4 if "table_graphics" in reasons else 0,
            largest_image_area_ratio=0.0,
            suspicious_reading_order="suspicious_reading_order" in reasons,
            reasons=reasons,
        ),
    )


def layouts(*page_reasons: tuple[str, ...]) -> tuple[PdfPageLayout, ...]:
    return tuple(
        PdfPageLayout(
            page_number=page_number,
            has_text="no_text" not in reasons,
            table_rectangle_count=4 if "table_graphics" in reasons else 0,
            largest_image_area_ratio=0.0,
            suspicious_reading_order="suspicious_reading_order" in reasons,
            reasons=reasons,
        )
        for page_number, reasons in enumerate(page_reasons, start=1)
    )


def avoid_real_pdf_rewrite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "devatlas.infrastructure.extraction.openai_pdf._select_pdf_pages",
        lambda content, _pages: content,
    )


def test_selected_pdf_contains_only_requested_pages_in_order() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=300, height=300)
    source = BytesIO()
    writer.write(source)

    selected = PdfReader(BytesIO(_select_pdf_pages(source.getvalue(), (3, 1))))

    assert len(selected.pages) == 2
    assert float(selected.pages[0].mediabox.width) == 300
    assert float(selected.pages[1].mediabox.width) == 100


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
    monkeypatch.setattr(
        "devatlas.infrastructure.extraction.openai_pdf.analyze_pdf_pages",
        lambda _content: layout(),
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
    avoid_real_pdf_rewrite(monkeypatch)
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
    monkeypatch.setattr(
        "devatlas.infrastructure.extraction.openai_pdf.analyze_pdf_pages",
        lambda _content: layouts((), ("no_text",)),
    )
    parse.return_value = SimpleNamespace(
        output_parsed=SimpleNamespace(
            pages=[
                SimpleNamespace(
                    page_number=2,
                    markdown="| Code | Value |\n| --- | --- |\n| DA-42 | Ready |",
                )
            ]
        )
    )
    extractor = OpenAIMultimodalDocumentExtractor(client, model="gpt-4.1-mini")

    result = await extractor.prepare(
        content=b"pdf", source_filename="scan.pdf", media_type="application/pdf"
    )

    assert result.page_spans == (PageSpan(1, 0, 7), PageSpan(2, 9, 57))
    assert result.normalized_text.startswith("Partial\n\n")
    assert "| DA-42 | Ready |" in result.normalized_text
    assert parse.await_args is not None
    request = parse.await_args.kwargs
    assert request["store"] is False
    assert request["input"][0]["content"][0]["detail"] == "high"
    assert (
        "attached page 1 = original page 2" in request["input"][0]["content"][1]["text"]
    )


@pytest.mark.asyncio
async def test_multimodal_extraction_rejects_duplicate_page_numbers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, parse = make_client()
    avoid_real_pdf_rewrite(monkeypatch)
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
    monkeypatch.setattr(
        "devatlas.infrastructure.extraction.openai_pdf.analyze_pdf_pages",
        lambda _content: layout("no_text"),
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

    with pytest.raises(DocumentExtractionUnavailableError, match="duplicate pages"):
        await extractor.prepare(
            content=b"pdf", source_filename="scan.pdf", media_type="application/pdf"
        )


@pytest.mark.asyncio
async def test_text_layer_table_still_uses_multimodal_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, parse = make_client()
    avoid_real_pdf_rewrite(monkeypatch)
    monkeypatch.setattr(
        "devatlas.infrastructure.extraction.openai_pdf.prepare_document",
        lambda **_kwargs: PreparedTextDocument(
            source_filename="table.pdf",
            media_type="application/pdf",
            normalized_text="Component Code State Owner",
            content_checksum="checksum",
            byte_size=3,
            character_count=26,
            page_spans=(PageSpan(1, 0, 26),),
        ),
    )
    monkeypatch.setattr(
        "devatlas.infrastructure.extraction.openai_pdf.analyze_pdf_pages",
        lambda _content: layout("table_graphics"),
    )
    parse.return_value = SimpleNamespace(
        output_parsed=SimpleNamespace(
            pages=[SimpleNamespace(page_number=1, markdown="| A | B |")]
        )
    )
    extractor = OpenAIMultimodalDocumentExtractor(client)

    result = await extractor.prepare(
        content=b"pdf", source_filename="table.pdf", media_type="application/pdf"
    )

    assert result.normalized_text == "| A | B |"
    parse.assert_awaited_once()
