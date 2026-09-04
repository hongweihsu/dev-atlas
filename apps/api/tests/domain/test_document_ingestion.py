import pytest

from devatlas.domain.document_ingestion import (
    DEFAULT_MAX_TEXT_BYTES,
    DocumentValidationCode,
    DocumentValidationError,
    PreparedTextDocument,
    prepare_text_document,
)
from devatlas.domain.text_processing import content_checksum


def test_prepare_text_document_returns_normalized_metadata() -> None:
    content = "  第一段\r\n\r\nSecond paragraph.  ".encode()
    normalized_text = "第一段\n\nSecond paragraph."

    prepared = prepare_text_document(
        content=content,
        source_filename="notes.TXT",
        media_type="text/plain",
    )

    assert prepared == PreparedTextDocument(
        source_filename="notes.TXT",
        media_type="text/plain",
        normalized_text=normalized_text,
        content_checksum=content_checksum(normalized_text),
        byte_size=len(content),
        character_count=len(normalized_text),
    )


@pytest.mark.parametrize(
    ("source_filename", "media_type"),
    [
        ("notes.pdf", "text/plain"),
        ("notes.txt", "application/pdf"),
        ("notes.txt", "application/octet-stream"),
        ("", "text/plain"),
    ],
)
def test_prepare_text_document_rejects_unsupported_type(
    source_filename: str,
    media_type: str,
) -> None:
    with pytest.raises(DocumentValidationError) as captured:
        prepare_text_document(
            content=b"content",
            source_filename=source_filename,
            media_type=media_type,
        )

    assert captured.value.code is DocumentValidationCode.UNSUPPORTED_TYPE
    assert str(captured.value) == "only UTF-8 text/plain .txt files are supported"


def test_prepare_text_document_rejects_content_over_byte_limit() -> None:
    with pytest.raises(DocumentValidationError) as captured:
        prepare_text_document(
            content=b"1234",
            source_filename="notes.txt",
            media_type="text/plain",
            max_bytes=3,
        )

    assert captured.value.code is DocumentValidationCode.FILE_TOO_LARGE
    assert str(captured.value) == "file exceeds the 3-byte limit"


def test_prepare_text_document_accepts_content_at_byte_limit() -> None:
    prepared = prepare_text_document(
        content=b"123",
        source_filename="notes.txt",
        media_type="text/plain",
        max_bytes=3,
    )

    assert prepared.byte_size == 3


def test_prepare_text_document_rejects_invalid_utf8() -> None:
    with pytest.raises(DocumentValidationError) as captured:
        prepare_text_document(
            content=b"\xff",
            source_filename="notes.txt",
            media_type="text/plain",
        )

    assert captured.value.code is DocumentValidationCode.INVALID_UTF8
    assert str(captured.value) == "file content must be valid UTF-8"


@pytest.mark.parametrize("content", [b"", b"  \r\n\t"])
def test_prepare_text_document_rejects_empty_normalized_content(
    content: bytes,
) -> None:
    with pytest.raises(DocumentValidationError) as captured:
        prepare_text_document(
            content=content,
            source_filename="notes.txt",
            media_type="text/plain",
        )

    assert captured.value.code is DocumentValidationCode.EMPTY_CONTENT
    assert str(captured.value) == "file content must not be empty after normalization"


def test_prepare_text_document_rejects_invalid_configured_limit() -> None:
    with pytest.raises(ValueError, match="max_bytes must be greater than zero"):
        prepare_text_document(
            content=b"content",
            source_filename="notes.txt",
            media_type="text/plain",
            max_bytes=0,
        )


def test_default_text_limit_is_one_mebibyte() -> None:
    assert DEFAULT_MAX_TEXT_BYTES == 1_048_576
