import json
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from devatlas.application.ports.generation import EvidenceSource
from devatlas.application.ports.retrieval import RetrievedChunk

MAX_ANSWER_CONTEXT_CHARACTERS = 12_000


class InvalidContextBudgetError(ValueError):
    """Raised when a context budget cannot hold the context envelope."""


@dataclass(frozen=True, slots=True)
class ContextDiagnostics:
    """Observable properties of the exact ranked context sent to generation."""

    candidate_count: int
    selected_count: int
    rendered_characters: int
    budget_utilization: float
    represented_document_count: int
    max_document_share: float
    overlapping_neighbor_pairs: int
    overlapping_characters: int
    candidates_excluded_by_budget: int


def build_bounded_context(
    chunks: Sequence[RetrievedChunk],
    *,
    max_characters: int = MAX_ANSWER_CONTEXT_CHARACTERS,
) -> tuple[str, tuple[EvidenceSource, ...]]:
    """Render a ranked prefix of unique chunks within an exact character budget."""
    empty_context = _render_context(())
    if max_characters < len(empty_context):
        raise InvalidContextBudgetError(
            f"max_characters must be at least {len(empty_context)}"
        )

    selected: list[EvidenceSource] = []
    seen_chunk_ids = set()

    for chunk in chunks:
        if chunk.chunk_id in seen_chunk_ids:
            continue

        source = _to_evidence_source(chunk, citation_id=f"S{len(selected) + 1}")
        candidate = (*selected, source)
        rendered = _render_context(candidate)
        if len(rendered) > max_characters:
            break

        selected.append(source)
        seen_chunk_ids.add(chunk.chunk_id)

    sources = tuple(selected)
    return _render_context(sources), sources


def diagnose_bounded_context(
    chunks: Sequence[RetrievedChunk],
    *,
    max_characters: int = MAX_ANSWER_CONTEXT_CHARACTERS,
) -> ContextDiagnostics:
    """Measure context selection without changing its production policy."""
    rendered, sources = build_bounded_context(
        chunks,
        max_characters=max_characters,
    )
    unique_candidate_count = len({chunk.chunk_id for chunk in chunks})
    document_counts: dict[UUID, int] = {}
    for source in sources:
        document_counts[source.document_id] = (
            document_counts.get(source.document_id, 0) + 1
        )

    overlapping_neighbor_pairs = 0
    overlapping_characters = 0
    for index, left in enumerate(sources):
        for right in sources[index + 1 :]:
            different_version = left.version_id != right.version_id
            not_neighbors = abs(left.ordinal - right.ordinal) != 1
            if different_version or not_neighbors:
                continue
            overlap = max(
                0,
                min(left.end_offset, right.end_offset)
                - max(left.start_offset, right.start_offset),
            )
            if overlap:
                overlapping_neighbor_pairs += 1
                overlapping_characters += overlap

    selected_count = len(sources)
    return ContextDiagnostics(
        candidate_count=unique_candidate_count,
        selected_count=selected_count,
        rendered_characters=len(rendered),
        budget_utilization=len(rendered) / max_characters,
        represented_document_count=len(document_counts),
        max_document_share=(
            max(document_counts.values()) / selected_count if selected_count else 0.0
        ),
        overlapping_neighbor_pairs=overlapping_neighbor_pairs,
        overlapping_characters=overlapping_characters,
        candidates_excluded_by_budget=unique_candidate_count - selected_count,
    )


def _to_evidence_source(
    chunk: RetrievedChunk,
    *,
    citation_id: str,
) -> EvidenceSource:
    return EvidenceSource(
        citation_id=citation_id,
        document_id=chunk.document_id,
        document_title=chunk.document_title,
        version_id=chunk.version_id,
        version_number=chunk.version_number,
        chunk_id=chunk.chunk_id,
        ordinal=chunk.ordinal,
        text=chunk.text,
        start_offset=chunk.start_offset,
        end_offset=chunk.end_offset,
    )


def _render_context(sources: Sequence[EvidenceSource]) -> str:
    payload = {
        "sources": [
            {
                "citation_id": source.citation_id,
                "document_id": str(source.document_id),
                "document_title": source.document_title,
                "version_id": str(source.version_id),
                "version_number": source.version_number,
                "chunk_id": str(source.chunk_id),
                "ordinal": source.ordinal,
                "start_offset": source.start_offset,
                "end_offset": source.end_offset,
                "content": source.text,
            }
            for source in sources
        ]
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
