from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from retrieval_works.api.dependencies.authentication import CurrentWorkspace
from retrieval_works.api.routes.answers import AnswerCitationResponse
from retrieval_works.api.routes.knowledge_bases import get_manage_knowledge_bases
from retrieval_works.application.corrective_answer_documents import (
    CorrectiveAnswerDocuments,
    CorrectiveAnswerDocumentsCommand,
)
from retrieval_works.application.ports.correction import (
    CorrectiveQueryProviderUnavailableError,
)
from retrieval_works.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProviderUnavailableError,
)
from retrieval_works.application.ports.generation import (
    AnswerGeneratorUnavailableError,
    InvalidGeneratedAnswerError,
)
from retrieval_works.application.ports.knowledge_bases import (
    InvalidKnowledgeBaseScopeError,
)
from retrieval_works.application.search_documents import InvalidSearchQueryError
from retrieval_works.infrastructure.observability import HttpMetrics


class CorrectiveAnswerRequest(BaseModel):
    question: str
    limit: int = 5
    knowledge_base_ids: list[UUID] = Field(default_factory=list)


class CorrectiveAnswerResponse(BaseModel):
    answer: str
    has_sufficient_evidence: bool
    citations: list[AnswerCitationResponse]
    correction_applied: bool
    corrective_query: str | None


router = APIRouter(prefix="/corrective-answers", tags=["corrective-answers"])


def get_corrective_answer_documents(request: Request) -> CorrectiveAnswerDocuments:
    service = getattr(request.app.state, "corrective_answer_documents", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "corrective_answers_unavailable",
                "message": "corrective answers are not configured",
            },
        )
    return cast(CorrectiveAnswerDocuments, service)


CorrectiveAnswerService = Annotated[
    CorrectiveAnswerDocuments, Depends(get_corrective_answer_documents)
]


@router.post("", response_model=CorrectiveAnswerResponse)
async def corrective_answer(
    payload: CorrectiveAnswerRequest,
    request: Request,
    service: CorrectiveAnswerService,
    workspace: CurrentWorkspace,
) -> CorrectiveAnswerResponse:
    try:
        scope: tuple[UUID, ...] = ()
        if payload.knowledge_base_ids:
            scope = await get_manage_knowledge_bases(request).resolve_scope(
                workspace.workspace_id, tuple(payload.knowledge_base_ids)
            )
        result = await service.execute(
            CorrectiveAnswerDocumentsCommand(
                question=payload.question,
                workspace_id=workspace.workspace_id,
                limit=payload.limit,
                knowledge_base_ids=scope,
            )
        )
    except (InvalidKnowledgeBaseScopeError, InvalidSearchQueryError) as error:
        _record_outcome(request, "invalid_request")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_corrective_answer", "message": str(error)},
        ) from error
    except (EmbeddingBatchError, InvalidGeneratedAnswerError) as error:
        _record_outcome(request, "invalid_provider_response")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_corrective_response", "message": str(error)},
        ) from error
    except (
        AnswerGeneratorUnavailableError,
        CorrectiveQueryProviderUnavailableError,
        EmbeddingProviderUnavailableError,
    ) as error:
        _record_outcome(request, "provider_unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "corrective_provider_unavailable", "message": str(error)},
        ) from error

    answer = result.result
    if result.correction_applied:
        outcome = (
            "corrected_sufficient"
            if answer.has_sufficient_evidence
            else "corrected_insufficient"
        )
    else:
        outcome = (
            "first_pass_sufficient"
            if answer.has_sufficient_evidence
            else "uncorrected_insufficient"
        )
    _record_outcome(request, outcome)
    return CorrectiveAnswerResponse(
        answer=answer.answer,
        has_sufficient_evidence=answer.has_sufficient_evidence,
        correction_applied=result.correction_applied,
        corrective_query=result.corrective_query,
        citations=[
            AnswerCitationResponse(
                citation_id=item.citation_id,
                document_id=str(item.document_id),
                document_title=item.document_title,
                version_id=str(item.version_id),
                version_number=item.version_number,
                chunk_id=str(item.chunk_id),
                ordinal=item.ordinal,
                text=item.text,
                start_offset=item.start_offset,
                end_offset=item.end_offset,
                page_start=item.page_start,
                page_end=item.page_end,
            )
            for item in answer.citations
        ],
    )


def _record_outcome(request: Request, outcome: str) -> None:
    metrics: HttpMetrics = request.app.state.http_metrics
    metrics.record_workflow(workflow="corrective_answer", outcome=outcome)
