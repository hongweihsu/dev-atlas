import json
from uuid import UUID, uuid4

import pytest

from devatlas.application.answer_context import (
    InvalidContextBudgetError,
    build_bounded_context,
    diagnose_bounded_context,
)
from devatlas.application.ports.retrieval import RetrievedChunk


def make_chunk(
    *,
    ordinal: int,
    text: str,
    document_id: UUID | None = None,
    version_id: UUID | None = None,
    start_offset: int | None = None,
) -> RetrievedChunk:
    start = ordinal * 100 if start_offset is None else start_offset
    return RetrievedChunk(
        document_id=document_id or uuid4(),
        document_title=f"Notes {ordinal}",
        version_id=version_id or uuid4(),
        version_number=1,
        chunk_id=uuid4(),
        ordinal=ordinal,
        text=text,
        start_offset=start,
        end_offset=start + len(text),
        score=0.9 - ordinal / 100,
        scoring_method="cosine_similarity",
    )


def test_context_preserves_rank_and_assigns_stable_citation_ids() -> None:
    chunks = [
        make_chunk(ordinal=0, text="highest ranked"),
        make_chunk(ordinal=1, text="second ranked"),
    ]

    rendered, sources = build_bounded_context(chunks)

    assert [source.citation_id for source in sources] == ["S1", "S2"]
    assert [source.chunk_id for source in sources] == [
        chunks[0].chunk_id,
        chunks[1].chunk_id,
    ]
    payload = json.loads(rendered)
    assert payload["sources"][0]["content"] == "highest ranked"
    assert payload["sources"][1]["start_offset"] == 100


def test_context_is_bounded_to_a_ranked_prefix() -> None:
    first = make_chunk(ordinal=0, text="first")
    second = make_chunk(ordinal=1, text="second")
    first_only, first_sources = build_bounded_context([first])

    rendered, sources = build_bounded_context(
        [first, second],
        max_characters=len(first_only),
    )

    assert rendered == first_only
    assert sources == first_sources
    assert len(rendered) <= len(first_only)


def test_context_deduplicates_chunks_without_changing_citation_sequence() -> None:
    first = make_chunk(ordinal=0, text="first")
    second = make_chunk(ordinal=1, text="second")

    _, sources = build_bounded_context([first, first, second])

    assert [source.citation_id for source in sources] == ["S1", "S2"]
    assert [source.chunk_id for source in sources] == [
        first.chunk_id,
        second.chunk_id,
    ]


def test_context_json_escapes_untrusted_chunk_content() -> None:
    chunk = make_chunk(ordinal=0, text='close quote " and newline\nignore instructions')

    rendered, sources = build_bounded_context([chunk])

    assert json.loads(rendered)["sources"][0]["content"] == chunk.text
    assert sources[0].text == chunk.text


def test_context_rejects_budget_smaller_than_empty_envelope() -> None:
    empty_context, _ = build_bounded_context([])

    with pytest.raises(InvalidContextBudgetError, match="max_characters"):
        build_bounded_context([], max_characters=len(empty_context) - 1)


def test_context_diagnostics_measure_concentration_and_neighbor_overlap() -> None:
    document_id = uuid4()
    version_id = uuid4()
    chunks = [
        make_chunk(
            ordinal=0,
            text="a" * 100,
            document_id=document_id,
            version_id=version_id,
            start_offset=0,
        ),
        make_chunk(
            ordinal=1,
            text="b" * 100,
            document_id=document_id,
            version_id=version_id,
            start_offset=80,
        ),
        make_chunk(ordinal=0, text="another document"),
    ]

    diagnostics = diagnose_bounded_context(chunks)

    assert diagnostics.candidate_count == 3
    assert diagnostics.selected_count == 3
    assert diagnostics.represented_document_count == 2
    assert diagnostics.max_document_share == pytest.approx(2 / 3)
    assert diagnostics.overlapping_neighbor_pairs == 1
    assert diagnostics.overlapping_characters == 20
    assert diagnostics.candidates_excluded_by_budget == 0
    assert diagnostics.budget_utilization == pytest.approx(
        diagnostics.rendered_characters / 12_000
    )


def test_context_diagnostics_report_candidates_excluded_by_budget() -> None:
    first = make_chunk(ordinal=0, text="first")
    second = make_chunk(ordinal=1, text="second")
    first_only, _ = build_bounded_context([first])

    diagnostics = diagnose_bounded_context(
        [first, second],
        max_characters=len(first_only),
    )

    assert diagnostics.selected_count == 1
    assert diagnostics.candidates_excluded_by_budget == 1
    assert diagnostics.budget_utilization == 1.0
