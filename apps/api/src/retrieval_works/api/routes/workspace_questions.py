from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from retrieval_works.api.dependencies.authentication import CurrentWorkspace
from retrieval_works.application.answer_workspace_question import (
    AnswerWorkspaceQuestion,
    AnswerWorkspaceQuestionCommand,
)
from retrieval_works.application.ports.tool_calling import (
    InvalidToolCallError,
    InvalidWorkspaceQuestionError,
    WorkspaceToolProviderUnavailableError,
)
from retrieval_works.infrastructure.observability import HttpMetrics


class WorkspaceQuestionRequest(BaseModel):
    question: str


class ExecutedToolResponse(BaseModel):
    name: str


class WorkspaceQuestionResponse(BaseModel):
    answer: str
    tools: list[ExecutedToolResponse]


router = APIRouter(prefix="/workspace-questions", tags=["workspace-questions"])


def get_answer_workspace_question(request: Request) -> AnswerWorkspaceQuestion:
    service = getattr(request.app.state, "answer_workspace_question", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "workspace_questions_unavailable",
                "message": "workspace tool calling is not configured",
            },
        )
    return cast(AnswerWorkspaceQuestion, service)


WorkspaceQuestionService = Annotated[
    AnswerWorkspaceQuestion, Depends(get_answer_workspace_question)
]


@router.post("", response_model=WorkspaceQuestionResponse)
async def answer_workspace_question(
    payload: WorkspaceQuestionRequest,
    request: Request,
    service: WorkspaceQuestionService,
    workspace: CurrentWorkspace,
) -> WorkspaceQuestionResponse:
    try:
        result = await service.execute(
            AnswerWorkspaceQuestionCommand(
                question=payload.question,
                workspace_id=workspace.workspace_id,
            )
        )
    except InvalidWorkspaceQuestionError as error:
        _record_outcome(request, "invalid_question")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_workspace_question", "message": str(error)},
        ) from error
    except InvalidToolCallError as error:
        _record_outcome(request, "invalid_tool_call")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_tool_call", "message": str(error)},
        ) from error
    except WorkspaceToolProviderUnavailableError as error:
        _record_outcome(request, "provider_unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "tool_provider_unavailable", "message": str(error)},
        ) from error

    _record_outcome(request, "tool_executed")
    return WorkspaceQuestionResponse(
        answer=result.text,
        tools=[ExecutedToolResponse(name=tool.name) for tool in result.tools],
    )


def _record_outcome(request: Request, outcome: str) -> None:
    metrics: HttpMetrics = request.app.state.http_metrics
    metrics.record_workflow(workflow="workspace_question", outcome=outcome)
