from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from devatlas.api.dependencies.authentication import CurrentWorkspace, WritableWorkspace
from devatlas.application.manage_knowledge_bases import (
    InvalidKnowledgeBaseNameError,
    ManageKnowledgeBases,
)
from devatlas.application.ports.knowledge_bases import (
    DuplicateKnowledgeBaseNameError,
)


class KnowledgeBaseResponse(BaseModel):
    id: UUID
    name: str
    is_default: bool
    document_count: int


class CreateKnowledgeBaseRequest(BaseModel):
    name: str


router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


def get_manage_knowledge_bases(request: Request) -> ManageKnowledgeBases:
    service = getattr(request.app.state, "manage_knowledge_bases", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "knowledge_bases_unavailable",
                "message": "knowledge base management is not configured",
            },
        )
    return cast(ManageKnowledgeBases, service)


KnowledgeBaseService = Annotated[
    ManageKnowledgeBases, Depends(get_manage_knowledge_bases)
]


def _response(summary: object) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse.model_validate(summary, from_attributes=True)


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    service: KnowledgeBaseService,
    workspace: CurrentWorkspace,
) -> list[KnowledgeBaseResponse]:
    return [
        _response(summary) for summary in await service.list(workspace.workspace_id)
    ]


@router.post(
    "", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED
)
async def create_knowledge_base(
    request: CreateKnowledgeBaseRequest,
    service: KnowledgeBaseService,
    workspace: WritableWorkspace,
) -> KnowledgeBaseResponse:
    try:
        summary = await service.create(workspace.workspace_id, request.name)
    except InvalidKnowledgeBaseNameError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_knowledge_base_name", "message": str(error)},
        ) from error
    except DuplicateKnowledgeBaseNameError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "duplicate_knowledge_base_name", "message": str(error)},
        ) from error
    return _response(summary)
