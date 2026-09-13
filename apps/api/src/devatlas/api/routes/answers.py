from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from devatlas.api.dependencies.authentication import CurrentWorkspace
from devatlas.api.routes.knowledge_bases import get_manage_knowledge_bases
from devatlas.application.answer_documents import (
    AnswerDocuments,
    AnswerDocumentsCommand,
)
from devatlas.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProviderUnavailableError,
)
from devatlas.application.ports.generation import (
    AnswerGeneratorUnavailableError,
    InvalidGeneratedAnswerError,
)
from devatlas.application.ports.knowledge_bases import InvalidKnowledgeBaseScopeError
from devatlas.application.search_documents import InvalidSearchQueryError


class AnswerRequest(BaseModel):
    question: str
    limit: int = 5
    knowledge_base_ids: list[UUID] = Field(default_factory=list)


class AnswerCitationResponse(BaseModel):
    citation_id: str
    document_id: str
    document_title: str
    version_id: str
    version_number: int
    chunk_id: str
    ordinal: int
    text: str
    start_offset: int
    end_offset: int
    page_start: int | None
    page_end: int | None


class AnswerResponse(BaseModel):
    answer: str
    has_sufficient_evidence: bool
    citations: list[AnswerCitationResponse]


router = APIRouter(prefix="/answers", tags=["answers"])


def get_answer_documents(request: Request) -> AnswerDocuments:
    service = getattr(request.app.state, "answer_documents", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "answers_unavailable",
                "message": "document answers are not configured",
            },
        )
    return cast(AnswerDocuments, service)


AnswerService = Annotated[AnswerDocuments, Depends(get_answer_documents)]


@router.post("", response_model=AnswerResponse)
async def answer_documents(
    payload: AnswerRequest,
    request: Request,
    service: AnswerService,
    workspace: CurrentWorkspace,
) -> AnswerResponse:
    try:
        scope: tuple[UUID, ...] = ()
        if payload.knowledge_base_ids:
            scope = await get_manage_knowledge_bases(request).resolve_scope(
                workspace.workspace_id, tuple(payload.knowledge_base_ids)
            )
        result = await service.execute(
            AnswerDocumentsCommand(
                question=payload.question,
                workspace_id=workspace.workspace_id,
                limit=payload.limit,
                knowledge_base_ids=scope,
            )
        )
    except InvalidKnowledgeBaseScopeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_knowledge_base_scope", "message": str(error)},
        ) from error
    except InvalidSearchQueryError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_question", "message": str(error)},
        ) from error
    except EmbeddingBatchError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_embedding_response", "message": str(error)},
        ) from error
    except InvalidGeneratedAnswerError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_answer_response", "message": str(error)},
        ) from error
    except EmbeddingProviderUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "embedding_unavailable", "message": str(error)},
        ) from error
    except AnswerGeneratorUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "answer_provider_unavailable", "message": str(error)},
        ) from error

    return AnswerResponse(
        answer=result.answer,
        has_sufficient_evidence=result.has_sufficient_evidence,
        citations=[
            AnswerCitationResponse(
                citation_id=citation.citation_id,
                document_id=str(citation.document_id),
                document_title=citation.document_title,
                version_id=str(citation.version_id),
                version_number=citation.version_number,
                chunk_id=str(citation.chunk_id),
                ordinal=citation.ordinal,
                text=citation.text,
                start_offset=citation.start_offset,
                end_offset=citation.end_offset,
                page_start=citation.page_start,
                page_end=citation.page_end,
            )
            for citation in result.citations
        ],
    )
