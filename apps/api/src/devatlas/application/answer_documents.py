from dataclasses import dataclass

from devatlas.application.answer_context import build_bounded_context
from devatlas.application.ports.generation import (
    AnswerGenerationRequest,
    AnswerGenerator,
    EvidenceSource,
    InvalidGeneratedAnswerError,
)
from devatlas.application.search_documents import (
    SearchDocuments,
    SearchDocumentsCommand,
)

NO_EVIDENCE_ANSWER = "I don't have enough evidence in the indexed documents."


@dataclass(frozen=True, slots=True)
class AnswerDocumentsCommand:
    question: str
    limit: int = 5


@dataclass(frozen=True, slots=True)
class AnswerDocumentsResult:
    answer: str
    citations: tuple[EvidenceSource, ...]
    has_sufficient_evidence: bool


class AnswerDocuments:
    def __init__(
        self,
        *,
        search_documents: SearchDocuments,
        generator: AnswerGenerator,
    ) -> None:
        self._search_documents = search_documents
        self._generator = generator

    async def execute(self, command: AnswerDocumentsCommand) -> AnswerDocumentsResult:
        chunks = await self._search_documents.execute(
            SearchDocumentsCommand(query=command.question, limit=command.limit)
        )
        context, sources = build_bounded_context(chunks)
        if not sources:
            return AnswerDocumentsResult(
                answer=NO_EVIDENCE_ANSWER,
                citations=(),
                has_sufficient_evidence=False,
            )

        generated = await self._generator.generate(
            AnswerGenerationRequest(
                question=command.question.strip(),
                context=context,
                sources=sources,
            )
        )
        answer = generated.text.strip()
        if not answer:
            raise InvalidGeneratedAnswerError("answer text must not be empty")

        sources_by_id = {source.citation_id: source for source in sources}
        unknown_ids = set(generated.citation_ids) - sources_by_id.keys()
        if unknown_ids:
            unknown = ", ".join(sorted(unknown_ids))
            raise InvalidGeneratedAnswerError(f"unknown citation IDs: {unknown}")

        citation_ids = tuple(dict.fromkeys(generated.citation_ids))
        if generated.has_sufficient_evidence and not citation_ids:
            raise InvalidGeneratedAnswerError(
                "a generated answer must cite at least one evidence source"
            )
        if not generated.has_sufficient_evidence and citation_ids:
            raise InvalidGeneratedAnswerError(
                "an insufficient-evidence answer must not cite a source"
            )

        return AnswerDocumentsResult(
            answer=answer,
            citations=tuple(sources_by_id[item] for item in citation_ids),
            has_sufficient_evidence=generated.has_sufficient_evidence,
        )
