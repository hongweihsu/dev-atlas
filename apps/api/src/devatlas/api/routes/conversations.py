from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from devatlas.api.dependencies.authentication import CurrentWorkspace
from devatlas.api.routes.answers import AnswerCitationResponse
from devatlas.api.routes.knowledge_bases import get_manage_knowledge_bases
from devatlas.application.manage_conversations import (
    AskConversationCommand,
    ManageConversations,
)
from devatlas.application.ports.conversations import (
    ConversationNotFoundError,
    ConversationSummary,
    ConversationTurn,
    InvalidConversationError,
    QuestionContextualizerUnavailableError,
)
from devatlas.application.ports.embedding import (
    EmbeddingBatchError,
    EmbeddingProviderUnavailableError,
)
from devatlas.application.ports.generation import (
    AnswerGeneratorUnavailableError,
    EvidenceSource,
    InvalidGeneratedAnswerError,
)
from devatlas.application.ports.knowledge_bases import InvalidKnowledgeBaseScopeError
from devatlas.application.search_documents import InvalidSearchQueryError


class CreateConversationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ConversationSummaryResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class AskConversationRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)
    knowledge_base_ids: list[UUID] = Field(default_factory=list)


class ConversationTurnResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    ordinal: int
    question: str
    standalone_question: str
    answer: str
    has_sufficient_evidence: bool
    citations: list[AnswerCitationResponse]
    created_at: datetime


router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_manage_conversations(request: Request) -> ManageConversations:
    service = getattr(request.app.state, "manage_conversations", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "conversations_unavailable",
                "message": "conversation memory is not configured",
            },
        )
    return cast(ManageConversations, service)


ConversationService = Annotated[ManageConversations, Depends(get_manage_conversations)]


def _summary_response(item: ConversationSummary) -> ConversationSummaryResponse:
    return ConversationSummaryResponse(
        id=item.id,
        title=item.title,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _citation_response(source: EvidenceSource) -> AnswerCitationResponse:
    return AnswerCitationResponse(
        citation_id=source.citation_id,
        document_id=str(source.document_id),
        document_title=source.document_title,
        version_id=str(source.version_id),
        version_number=source.version_number,
        chunk_id=str(source.chunk_id),
        ordinal=source.ordinal,
        text=source.text,
        start_offset=source.start_offset,
        end_offset=source.end_offset,
        page_start=source.page_start,
        page_end=source.page_end,
    )


def _turn_response(item: ConversationTurn) -> ConversationTurnResponse:
    return ConversationTurnResponse(
        id=item.id,
        conversation_id=item.conversation_id,
        ordinal=item.ordinal,
        question=item.question,
        standalone_question=item.standalone_question,
        answer=item.answer,
        has_sufficient_evidence=item.has_sufficient_evidence,
        citations=[_citation_response(source) for source in item.citations],
        created_at=item.created_at,
    )


@router.post(
    "", response_model=ConversationSummaryResponse, status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    payload: CreateConversationRequest,
    service: ConversationService,
    workspace: CurrentWorkspace,
) -> ConversationSummaryResponse:
    try:
        item = await service.create(
            workspace_id=workspace.workspace_id,
            user_id=workspace.user_id,
            title=payload.title,
        )
    except InvalidConversationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_conversation", "message": str(error)},
        ) from error
    return _summary_response(item)


@router.get("", response_model=list[ConversationSummaryResponse])
async def list_conversations(
    service: ConversationService, workspace: CurrentWorkspace
) -> list[ConversationSummaryResponse]:
    items = await service.list(
        workspace_id=workspace.workspace_id, user_id=workspace.user_id
    )
    return [_summary_response(item) for item in items]


@router.get("/{conversation_id}/turns", response_model=list[ConversationTurnResponse])
async def list_conversation_turns(
    conversation_id: UUID,
    service: ConversationService,
    workspace: CurrentWorkspace,
) -> list[ConversationTurnResponse]:
    try:
        items = await service.get_turns(
            conversation_id=conversation_id,
            workspace_id=workspace.workspace_id,
            user_id=workspace.user_id,
        )
    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "conversation_not_found", "message": str(error)},
        ) from error
    return [_turn_response(item) for item in items]


@router.post("/{conversation_id}/turns", response_model=ConversationTurnResponse)
async def ask_conversation(
    conversation_id: UUID,
    payload: AskConversationRequest,
    request: Request,
    service: ConversationService,
    workspace: CurrentWorkspace,
) -> ConversationTurnResponse:
    try:
        scope: tuple[UUID, ...] = ()
        if payload.knowledge_base_ids:
            scope = await get_manage_knowledge_bases(request).resolve_scope(
                workspace.workspace_id, tuple(payload.knowledge_base_ids)
            )
        item = await service.ask(
            AskConversationCommand(
                conversation_id=conversation_id,
                workspace_id=workspace.workspace_id,
                user_id=workspace.user_id,
                question=payload.question,
                limit=payload.limit,
                knowledge_base_ids=scope,
            )
        )
    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "conversation_not_found", "message": str(error)},
        ) from error
    except (InvalidConversationError, InvalidSearchQueryError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_question", "message": str(error)},
        ) from error
    except InvalidKnowledgeBaseScopeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_knowledge_base_scope", "message": str(error)},
        ) from error
    except (EmbeddingBatchError, InvalidGeneratedAnswerError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_model_response", "message": str(error)},
        ) from error
    except (
        EmbeddingProviderUnavailableError,
        AnswerGeneratorUnavailableError,
        QuestionContextualizerUnavailableError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "conversation_provider_unavailable", "message": str(error)},
        ) from error
    return _turn_response(item)
