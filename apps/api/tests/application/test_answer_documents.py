from uuid import uuid4

import pytest

from devatlas.application.answer_documents import (
    NO_EVIDENCE_ANSWER,
    AnswerDocuments,
    AnswerDocumentsCommand,
)
from devatlas.application.ports.generation import (
    GeneratedAnswer,
    InvalidGeneratedAnswerError,
)
from devatlas.application.ports.retrieval import RetrievedChunk
from devatlas.application.search_documents import SearchDocuments
from tests.fakes import (
    DeterministicEmbeddingProvider,
    FakeChunkSearchRepository,
    RecordingAnswerGenerator,
)


def make_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        document_id=uuid4(),
        document_title="Architecture notes",
        version_id=uuid4(),
        version_number=1,
        chunk_id=uuid4(),
        ordinal=3,
        text="A unit of work defines a transaction boundary.",
        start_offset=100,
        end_offset=146,
        similarity=0.91,
    )


def make_use_case(
    chunks: list[RetrievedChunk],
    generated: GeneratedAnswer,
) -> tuple[AnswerDocuments, RecordingAnswerGenerator]:
    search = SearchDocuments(
        embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        repository=FakeChunkSearchRepository(chunks),
    )
    generator = RecordingAnswerGenerator(generated)
    return AnswerDocuments(search_documents=search, generator=generator), generator


@pytest.mark.asyncio
async def test_answer_searches_builds_context_and_returns_cited_sources() -> None:
    chunk = make_chunk()
    use_case, generator = make_use_case(
        [chunk],
        GeneratedAnswer(
            text="It defines the transaction boundary. [S1]",
            citation_ids=("S1",),
            has_sufficient_evidence=True,
        ),
    )

    result = await use_case.execute(AnswerDocumentsCommand(question="  What is it?  "))

    assert result.answer == "It defines the transaction boundary. [S1]"
    assert result.has_sufficient_evidence is True
    assert [source.chunk_id for source in result.citations] == [chunk.chunk_id]
    assert generator.requests[0].question == "What is it?"
    assert '"citation_id":"S1"' in generator.requests[0].context


@pytest.mark.asyncio
async def test_answer_does_not_call_generator_without_evidence() -> None:
    use_case, generator = make_use_case(
        [],
        GeneratedAnswer(
            text="unused", citation_ids=("S1",), has_sufficient_evidence=True
        ),
    )

    result = await use_case.execute(AnswerDocumentsCommand(question="unknown"))

    assert result.answer == NO_EVIDENCE_ANSWER
    assert result.has_sufficient_evidence is False
    assert result.citations == ()
    assert generator.requests == []


@pytest.mark.asyncio
async def test_answer_rejects_unknown_citation_ids() -> None:
    use_case, _ = make_use_case(
        [make_chunk()],
        GeneratedAnswer(
            text="Unsupported citation. [S99]",
            citation_ids=("S99",),
            has_sufficient_evidence=True,
        ),
    )

    with pytest.raises(InvalidGeneratedAnswerError, match="S99"):
        await use_case.execute(AnswerDocumentsCommand(question="What is it?"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "generated",
    [
        GeneratedAnswer(text="   ", citation_ids=("S1",), has_sufficient_evidence=True),
        GeneratedAnswer(
            text="No citation", citation_ids=(), has_sufficient_evidence=True
        ),
    ],
)
async def test_answer_rejects_incomplete_generated_output(
    generated: GeneratedAnswer,
) -> None:
    use_case, _ = make_use_case([make_chunk()], generated)

    with pytest.raises(InvalidGeneratedAnswerError):
        await use_case.execute(AnswerDocumentsCommand(question="What is it?"))


@pytest.mark.asyncio
async def test_answer_deduplicates_returned_citations_in_model_order() -> None:
    first = make_chunk()
    second = make_chunk()
    use_case, _ = make_use_case(
        [first, second],
        GeneratedAnswer(
            text="Combined. [S2] [S1]",
            citation_ids=("S2", "S1", "S2"),
            has_sufficient_evidence=True,
        ),
    )

    result = await use_case.execute(AnswerDocumentsCommand(question="Compare them"))

    assert [source.chunk_id for source in result.citations] == [
        second.chunk_id,
        first.chunk_id,
    ]


@pytest.mark.asyncio
async def test_answer_allows_explicit_insufficient_evidence_without_citations() -> None:
    use_case, _ = make_use_case(
        [make_chunk()],
        GeneratedAnswer(
            text="The indexed evidence is insufficient.",
            citation_ids=(),
            has_sufficient_evidence=False,
        ),
    )

    result = await use_case.execute(AnswerDocumentsCommand(question="Unrelated?"))

    assert result.answer == "The indexed evidence is insufficient."
    assert result.has_sufficient_evidence is False
    assert result.citations == ()


@pytest.mark.asyncio
async def test_answer_rejects_citations_when_evidence_is_marked_insufficient() -> None:
    use_case, _ = make_use_case(
        [make_chunk()],
        GeneratedAnswer(
            text="The evidence is insufficient. [S1]",
            citation_ids=("S1",),
            has_sufficient_evidence=False,
        ),
    )

    with pytest.raises(InvalidGeneratedAnswerError, match="must not cite"):
        await use_case.execute(AnswerDocumentsCommand(question="Unrelated?"))
