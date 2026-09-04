from dataclasses import dataclass
from enum import StrEnum

from devatlas.domain.text_processing import content_checksum, normalize_text

DEFAULT_MAX_TEXT_BYTES = 1024 * 1024


class DocumentValidationCode(StrEnum):
    UNSUPPORTED_TYPE = "unsupported_type"
    FILE_TOO_LARGE = "file_too_large"
    INVALID_UTF8 = "invalid_utf8"
    EMPTY_CONTENT = "empty_content"


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
