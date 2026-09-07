import json
from collections.abc import Sequence

from devatlas.application.ports.generation import EvidenceSource
from devatlas.application.ports.retrieval import RetrievedChunk

MAX_ANSWER_CONTEXT_CHARACTERS = 12_000


class InvalidContextBudgetError(ValueError):
    """Raised when a context budget cannot hold the context envelope."""


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
