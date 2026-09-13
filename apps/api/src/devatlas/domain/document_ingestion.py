from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from devatlas.domain.text_processing import content_checksum, normalize_text

DEFAULT_MAX_TEXT_BYTES = 1024 * 1024
DEFAULT_MAX_PDF_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_UPLOAD_BYTES = DEFAULT_MAX_PDF_BYTES


class DocumentValidationCode(StrEnum):
    UNSUPPORTED_TYPE = "unsupported_type"
    FILE_TOO_LARGE = "file_too_large"
    INVALID_UTF8 = "invalid_utf8"
    EMPTY_CONTENT = "empty_content"
    INVALID_PDF = "invalid_pdf"
    ENCRYPTED_PDF = "encrypted_pdf"
    NO_EXTRACTABLE_TEXT = "no_extractable_text"


class DocumentValidationError(ValueError):
    """Safe, stable validation failure that the API can map to an error response."""

    def __init__(self, code: DocumentValidationCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class PreparedTextDocument:
    """Validated, normalized text plus reproducible persistence metadata."""

    source_filename: str
    media_type: str
    normalized_text: str
    content_checksum: str
    byte_size: int
    character_count: int
    page_spans: tuple["PageSpan", ...] = ()


@dataclass(frozen=True, slots=True)
class PageSpan:
    page_number: int
    start_offset: int
    end_offset: int


def prepare_document(
    *, content: bytes, source_filename: str, media_type: str
) -> PreparedTextDocument:
    """Dispatch a supported upload to its package-backed extractor."""
    if source_filename.lower().endswith(".pdf") and media_type == "application/pdf":
        return prepare_pdf_document(
            content=content,
            source_filename=source_filename,
            media_type=media_type,
        )
    return prepare_text_document(
        content=content,
        source_filename=source_filename,
        media_type=media_type,
    )


def prepare_pdf_document(
    *,
    content: bytes,
    source_filename: str,
    media_type: str,
    max_bytes: int = DEFAULT_MAX_PDF_BYTES,
) -> PreparedTextDocument:
    if len(content) > max_bytes:
        raise DocumentValidationError(
            DocumentValidationCode.FILE_TOO_LARGE,
            f"file exceeds the {max_bytes}-byte limit",
        )
    try:
        reader = PdfReader(BytesIO(content))
    except PdfReadError as error:
        raise DocumentValidationError(
            DocumentValidationCode.INVALID_PDF, "file is not a readable PDF"
        ) from error
    if reader.is_encrypted:
        raise DocumentValidationError(
            DocumentValidationCode.ENCRYPTED_PDF,
            "encrypted PDF files are not supported",
        )

    page_texts = [normalize_text(page.extract_text() or "") for page in reader.pages]
    nonempty_pages = [
        (number, text) for number, text in enumerate(page_texts, start=1) if text
    ]
    if not nonempty_pages:
        raise DocumentValidationError(
            DocumentValidationCode.NO_EXTRACTABLE_TEXT,
            "PDF contains no extractable text; scanned-image OCR is not supported yet",
        )

    parts: list[str] = []
    spans: list[PageSpan] = []
    offset = 0
    for page_number, text in nonempty_pages:
        if parts:
            parts.append("\n\n")
            offset += 2
        start = offset
        parts.append(text)
        offset += len(text)
        spans.append(PageSpan(page_number, start, offset))
    normalized_text = "".join(parts)
    return PreparedTextDocument(
        source_filename=source_filename,
        media_type=media_type,
        normalized_text=normalized_text,
        content_checksum=content_checksum(normalized_text),
        byte_size=len(content),
        character_count=len(normalized_text),
        page_spans=tuple(spans),
    )


def prepare_text_document(
    *,
    content: bytes,
    source_filename: str,
    media_type: str,
    max_bytes: int = DEFAULT_MAX_TEXT_BYTES,
) -> PreparedTextDocument:
    """Validate and normalize a V1 UTF-8 text upload before ingestion."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero")
    if not source_filename.lower().endswith(".txt") or media_type != "text/plain":
        raise DocumentValidationError(
            DocumentValidationCode.UNSUPPORTED_TYPE,
            "only UTF-8 text/plain .txt files are supported",
        )
    if len(content) > max_bytes:
        raise DocumentValidationError(
            DocumentValidationCode.FILE_TOO_LARGE,
            f"file exceeds the {max_bytes}-byte limit",
        )

    try:
        decoded_text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DocumentValidationError(
            DocumentValidationCode.INVALID_UTF8,
            "file content must be valid UTF-8",
        ) from error

    normalized_text = normalize_text(decoded_text)
    if not normalized_text:
        raise DocumentValidationError(
            DocumentValidationCode.EMPTY_CONTENT,
            "file content must not be empty after normalization",
        )

    return PreparedTextDocument(
        source_filename=source_filename,
        media_type=media_type,
        normalized_text=normalized_text,
        content_checksum=content_checksum(normalized_text),
        byte_size=len(content),
        character_count=len(normalized_text),
    )
