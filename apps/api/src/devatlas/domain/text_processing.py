from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class TextChunk:
    """An ordered substring with offsets into normalized source text."""

    ordinal: int
    text: str
    start_offset: int
    end_offset: int


def normalize_text(text: str) -> str:
    """Normalize line endings and trim only the complete document edges."""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def content_checksum(normalized_text: str) -> str:
    """Return the lowercase SHA-256 digest of normalized UTF-8 text."""
    return sha256(normalized_text.encode("utf-8")).hexdigest()


def chunk_text(
    normalized_text: str,
    *,
    max_chars: int = 1000,
    overlap_chars: int = 100,
) -> list[TextChunk]:
    """Split normalized text into deterministic, ordered, traceable chunks."""
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must not be negative")
    if overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be less than max_chars")
    if not normalized_text:
        return []

    chunks: list[TextChunk] = []
    start = 0

    while start < len(normalized_text):
        hard_end = min(start + max_chars, len(normalized_text))
        end = (
            hard_end
            if hard_end == len(normalized_text)
            else _preferred_boundary(
                normalized_text,
                start=start,
                hard_end=hard_end,
                overlap_chars=overlap_chars,
            )
        )

        chunks.append(
            TextChunk(
                ordinal=len(chunks),
                text=normalized_text[start:end],
                start_offset=start,
                end_offset=end,
            )
        )

        if end == len(normalized_text):
            break
        start = end - overlap_chars

    return chunks


def _preferred_boundary(
    text: str,
    *,
    start: int,
    hard_end: int,
    overlap_chars: int,
) -> int:
    """Return the highest-priority viable boundary within the hard limit."""
    minimum_end = start + overlap_chars + 1

    for separator in ("\n\n", "\n"):
        position = text.rfind(separator, minimum_end - len(separator), hard_end)
        if position >= start:
            boundary = position + len(separator)
            if boundary >= minimum_end:
                return boundary

    for position in range(hard_end - 1, minimum_end - 2, -1):
        if text[position].isspace():
            return position + 1

    return hard_end
