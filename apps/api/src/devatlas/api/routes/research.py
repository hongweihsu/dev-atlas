from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from devatlas.api.dependencies.authentication import CurrentWorkspace
from devatlas.api.routes.answers import AnswerCitationResponse
from devatlas.application.ports.agentic_research import (
    InvalidResearchQuestionError,
    InvalidResearchResponseError,
    ResearchProviderUnavailableError,
)
from devatlas.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProviderUnavailableError,
)
from devatlas.application.run_agentic_research import (
    RunAgenticResearch,
    RunAgenticResearchCommand,
)
from devatlas.application.search_documents import InvalidSearchQueryError


class ResearchRequest(BaseModel):
    question: str


class ResearchStepResponse(BaseModel):
    ordinal: int
    tool_name: str
    summary: str


class ResearchResponse(BaseModel):
    answer: str
    has_sufficient_evidence: bool
    stop_reason: str
    steps: list[ResearchStepResponse]
    citations: list[AnswerCitationResponse]


router = APIRouter(prefix="/research", tags=["research"])


def get_run_agentic_research(request: Request) -> RunAgenticResearch:
    service = getattr(request.app.state, "run_agentic_research", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "research_unavailable",
                "message": "agentic research is not configured",
            },
        )
    return cast(RunAgenticResearch, service)


ResearchService = Annotated[RunAgenticResearch, Depends(get_run_agentic_research)]


@router.post("", response_model=ResearchResponse)
async def run_research(
    payload: ResearchRequest,
    service: ResearchService,
    workspace: CurrentWorkspace,
) -> ResearchResponse:
    try:
        result = await service.execute(
            RunAgenticResearchCommand(
                question=payload.question,
                workspace_id=workspace.workspace_id,
            )
        )
    except (InvalidResearchQuestionError, InvalidSearchQueryError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_research_question", "message": str(error)},
        ) from error
    except (InvalidResearchResponseError, EmbeddingBatchError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_research_response", "message": str(error)},
        ) from error
    except (
        ResearchProviderUnavailableError,
        EmbeddingProviderUnavailableError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "research_provider_unavailable", "message": str(error)},
        ) from error

    return ResearchResponse(
        answer=result.answer,
        has_sufficient_evidence=result.has_sufficient_evidence,
        stop_reason=result.stop_reason,
        steps=[
            ResearchStepResponse.model_validate(step, from_attributes=True)
            for step in result.steps
        ],
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
            for item in result.citations
        ],
    )
