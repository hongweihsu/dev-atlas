import pytest

from devatlas.domain.text_processing import (
    TextChunk,
    chunk_text,
    content_checksum,
    normalize_text,
)


def test_normalize_text_unifies_line_endings() -> None:
    assert normalize_text("a\r\nb\rc") == "a\nb\nc"


def test_normalize_text_trims_only_document_edges() -> None:
    assert normalize_text("  a  b  \n\nc  ") == "a  b  \n\nc"


def test_normalize_text_preserves_internal_unicode_content() -> None:
    assert normalize_text("  第一段\r\n\r\n第二段  ") == "第一段\n\n第二段"


def test_normalize_text_is_deterministic_and_idempotent() -> None:
    text = "  a\r\nb  "
    first = normalize_text(text)

    assert normalize_text(text) == first
    assert normalize_text(first) == first


def test_checksum_is_stable_after_line_ending_normalization() -> None:
    windows = normalize_text("hello\r\nworld")
    unix = normalize_text("hello\nworld")

    assert content_checksum(windows) == content_checksum(unix)


def test_checksum_changes_when_normalized_content_changes() -> None:
    assert content_checksum("hello") != content_checksum("hello!")


def test_checksum_is_lowercase_sha256_hex() -> None:
    checksum = content_checksum("hello")

    assert len(checksum) == 64
    assert checksum.isascii()
    assert all(character in "0123456789abcdef" for character in checksum)


def test_chunk_text_returns_empty_list_for_empty_normalized_text() -> None:
    assert chunk_text("") == []


def test_chunk_text_keeps_short_text_in_one_traceable_chunk() -> None:
    assert chunk_text("Hello 世界", max_chars=20, overlap_chars=5) == [
        TextChunk(
            ordinal=0,
            text="Hello 世界",
            start_offset=0,
            end_offset=8,
        )
    ]


def test_chunk_text_prefers_paragraph_then_newline_boundaries() -> None:
    text = "alpha beta\n\ngamma delta\nlast line"

    chunks = chunk_text(text, max_chars=18, overlap_chars=3)

    assert chunks[0].text == "alpha beta\n\n"
    assert chunks[0].end_offset == 12
    assert chunks[1].start_offset == 9
    assert chunks[1].text.endswith("\n")


def test_chunk_text_finds_paragraph_boundary_with_zero_overlap() -> None:
    chunks = chunk_text("a\n\nbcdefgh", max_chars=6, overlap_chars=0)

    assert chunks[0] == TextChunk(
        ordinal=0,
        text="a\n\n",
        start_offset=0,
        end_offset=3,
    )
    assert chunks[1].start_offset == 3


def test_chunk_text_falls_back_to_whitespace_then_hard_boundary() -> None:
    with_whitespace = chunk_text("alpha beta gamma", max_chars=11, overlap_chars=2)
    without_whitespace = chunk_text("abcdefghijklmno", max_chars=10, overlap_chars=2)

    assert with_whitespace[0].text == "alpha beta "
    assert without_whitespace[0].text == "abcdefghij"


def test_chunk_text_satisfies_v1_invariants() -> None:
    text = normalize_text(
        "第一段介紹 DevAtlas。\r\n\r\n"
        "第二段包含較長的內容，用來驗證 chunk 邊界、重疊和來源位置。\r\n"
        "Final paragraph without a trailing newline."
    )
    chunks = chunk_text(text, max_chars=32, overlap_chars=6)

    assert chunks
    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.text for chunk in chunks)
    assert all(
        0 <= chunk.start_offset < chunk.end_offset <= len(text) for chunk in chunks
    )
    assert all(
        chunk.text == text[chunk.start_offset : chunk.end_offset] for chunk in chunks
    )
    assert all(chunk.end_offset - chunk.start_offset <= 32 for chunk in chunks)
    assert all(
        current.start_offset < following.start_offset
        for current, following in zip(chunks, chunks[1:], strict=False)
    )

    covered_offsets = {
        offset
        for chunk in chunks
        for offset in range(chunk.start_offset, chunk.end_offset)
    }
    assert covered_offsets == set(range(len(text)))
    assert chunk_text(text, max_chars=32, overlap_chars=6) == chunks


@pytest.mark.parametrize(
    ("max_chars", "overlap_chars", "message"),
    [
        (0, 0, "max_chars must be greater than zero"),
        (-1, 0, "max_chars must be greater than zero"),
        (10, -1, "overlap_chars must not be negative"),
        (10, 10, "overlap_chars must be less than max_chars"),
        (10, 11, "overlap_chars must be less than max_chars"),
    ],
)
def test_chunk_text_rejects_invalid_parameters(
    max_chars: int,
    overlap_chars: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        chunk_text("content", max_chars=max_chars, overlap_chars=overlap_chars)
